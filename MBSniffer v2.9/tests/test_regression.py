import random
import threading
import unittest

from mb_capture import CaptureMixin
from mb_protocol import (
    SessionMetrics,
    append_crc,
    crc_ok,
    modbus_rtu_interframe_gap_seconds,
    parse_burst,
    split_capture_buffer,
)
from mb_slave_finder import (
    build_device_identification_probe,
    build_discovery_probe,
    device_identification_timeout_seconds,
    find_device_identification_response,
    find_discovery_response,
    format_device_identification,
    read_basic_device_identification,
)


def with_bad_crc(frame: bytes) -> bytes:
    damaged = bytearray(frame)
    damaged[-1] ^= 0xFF
    return bytes(damaged)


def device_id_response(
    slave=1,
    objects=None,
    *,
    more_follows=False,
    next_object_id=0,
    conformity=0x01,
):
    if objects is None:
        objects = {
            0x00: b"Schneider Electric",
            0x01: b"TEST-PRODUCT",
            0x02: b"1.2.3",
        }
    payload = bytearray((
        slave,
        0x2B,
        0x0E,
        0x01,
        conformity,
        0xFF if more_follows else 0x00,
        next_object_id,
        len(objects),
    ))
    for object_id, value in objects.items():
        value = bytes(value)
        payload.extend((int(object_id) & 0xFF, len(value)))
        payload.extend(value)
    return append_crc(bytes(payload))


class FakeSerial:
    """Minimal non-blocking serial fake for active Device ID regression tests."""

    def __init__(self, response_by_object):
        self.response_by_object = dict(response_by_object)
        self.rx = bytearray()
        self.writes = []

    @property
    def in_waiting(self):
        return len(self.rx)

    def reset_input_buffer(self):
        self.rx.clear()

    def reset_output_buffer(self):
        pass

    def write(self, data):
        data = bytes(data)
        self.writes.append(data)
        object_id = data[4] if len(data) >= 5 else 0
        response = self.response_by_object.get(object_id, b"")
        self.rx.extend(response)
        return len(data)

    def read(self, size):
        size = min(int(size), len(self.rx))
        chunk = bytes(self.rx[:size])
        del self.rx[:size]
        return chunk


class FakeSerialModule:
    class SerialTimeoutException(TimeoutError):
        pass

    class SerialException(OSError):
        pass


class StaticVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class DummyCapture:
    calculated_gap_ms = CaptureMixin.calculated_gap_ms

    def __init__(self, *, mode="Auto", baud="9600", data="8", parity="None", stop="1", manual="2.0"):
        self.gap_mode_var = StaticVar(mode)
        self.baud_var = StaticVar(baud)
        self.data_var = StaticVar(data)
        self.parity_var = StaticVar(parity)
        self.stop_var = StaticVar(stop)
        self.gap_ms_var = StaticVar(manual)


class TimingRegressionTests(unittest.TestCase):
    def test_t35_uses_character_time_at_or_below_19200(self):
        self.assertAlmostEqual(
            modbus_rtu_interframe_gap_seconds(9600, 11),
            3.5 * 11 / 9600,
            places=9,
        )
        self.assertAlmostEqual(
            modbus_rtu_interframe_gap_seconds(19200, 11),
            3.5 * 11 / 19200,
            places=9,
        )

    def test_t35_is_fixed_above_19200(self):
        for baud in (38400, 57600, 115200):
            with self.subTest(baud=baud):
                self.assertAlmostEqual(
                    modbus_rtu_interframe_gap_seconds(baud, 10),
                    0.001750,
                    places=9,
                )

    def test_sniffer_auto_gap_uses_fixed_1750_us_above_19200(self):
        capture = DummyCapture(baud="115200", parity="None", stop="1")
        self.assertAlmostEqual(capture.calculated_gap_ms(), 1.750, places=6)

    def test_sniffer_manual_gap_is_unchanged(self):
        capture = DummyCapture(mode="Manual", manual="2,75")
        self.assertAlmostEqual(capture.calculated_gap_ms(), 2.75, places=6)

    def test_device_id_timeout_covers_a_full_rtu_frame(self):
        timeout = device_identification_timeout_seconds(9600, "None", "1", 40)
        self.assertGreaterEqual(timeout, 256 * 10 / 9600 + 0.001750)


class ParserRegressionTests(unittest.TestCase):
    def test_crc_known_request(self):
        frame = build_discovery_probe(1, 3)
        self.assertTrue(crc_ok(frame))
        self.assertEqual(frame[:6], bytes.fromhex("01 03 00 00 00 01"))

    def test_invalid_frame_before_valid_frame_stays_crc_error(self):
        first = with_bad_crc(build_discovery_probe(1, 3))
        second = build_discovery_probe(2, 4)
        parts = split_capture_buffer(first + second)
        self.assertEqual(parts[0], (first, "REQUEST", "ERROR"))
        self.assertEqual(parts[1], (second, "REQUEST", "OK"))

    def test_long_unsynchronised_noise_recovers_next_valid_frame(self):
        noise = bytes([0xFF]) * 4000
        frame = build_discovery_probe(7, 3)
        parts = split_capture_buffer(noise + frame)
        self.assertEqual(parts[-1], (frame, "REQUEST", "OK"))
        self.assertTrue(parts[0][1].startswith("RAW/"))
        self.assertEqual(sum(len(part[0]) for part in parts), len(noise) + len(frame))

    def test_supported_function_code_shapes(self):
        frames = {
            "fc01_req": append_crc(bytes.fromhex("01 01 00 00 00 08")),
            "fc01_resp": append_crc(bytes.fromhex("01 01 01 5A")),
            "fc02_req": append_crc(bytes.fromhex("01 02 00 00 00 08")),
            "fc02_resp": append_crc(bytes.fromhex("01 02 01 A5")),
            "fc03_req": append_crc(bytes.fromhex("01 03 00 00 00 01")),
            "fc03_resp": append_crc(bytes.fromhex("01 03 02 00 2A")),
            "fc04_req": append_crc(bytes.fromhex("01 04 00 00 00 01")),
            "fc04_resp": append_crc(bytes.fromhex("01 04 02 00 2A")),
            "fc05": append_crc(bytes.fromhex("01 05 00 01 FF 00")),
            "fc06": append_crc(bytes.fromhex("01 06 00 01 00 2A")),
            "fc07_req": append_crc(bytes.fromhex("01 07")),
            "fc07_resp": append_crc(bytes.fromhex("01 07 AA")),
            "fc08": append_crc(bytes.fromhex("01 08 00 00 12 34")),
            "fc15_req": append_crc(bytes.fromhex("01 0F 00 00 00 08 01 5A")),
            "fc15_resp": append_crc(bytes.fromhex("01 0F 00 00 00 08")),
            "fc16_req": append_crc(bytes.fromhex("01 10 00 00 00 01 02 00 2A")),
            "fc16_resp": append_crc(bytes.fromhex("01 10 00 00 00 01")),
            "fc22": append_crc(bytes.fromhex("01 16 00 01 FF 00 00 2A")),
            "fc23_req": append_crc(bytes.fromhex(
                "01 17 00 00 00 01 00 10 00 01 02 00 2A"
            )),
            "fc23_resp": append_crc(bytes.fromhex("01 17 02 00 2A")),
            "exception": append_crc(bytes.fromhex("01 83 02")),
        }
        for name, frame in frames.items():
            with self.subTest(name=name):
                parts = split_capture_buffer(frame)
                self.assertEqual(len(parts), 1)
                self.assertEqual(parts[0][0], frame)
                self.assertEqual(parts[0][2], "OK")
                self.assertFalse(parts[0][1].startswith("RAW"))

    def test_random_noise_never_crashes_and_preserves_all_bytes(self):
        rng = random.Random(20260910)
        for _ in range(250):
            length = rng.randint(1, 512)
            data = bytes(rng.randrange(256) for _ in range(length))
            parts = split_capture_buffer(data)
            self.assertEqual(sum(len(part[0]) for part in parts), len(data))
            self.assertTrue(all(len(part[0]) > 0 for part in parts))

    def test_request_response_pairing_and_response_time(self):
        req = parse_burst(
            append_crc(bytes.fromhex("01 03 00 00 00 01")),
            "12:00:00.000",
            "BUS",
            100.000,
        )[0]
        resp = parse_burst(
            append_crc(bytes.fromhex("01 03 02 00 2A")),
            "12:00:00.125",
            "BUS",
            100.125,
        )[0]
        req["_view_seq"] = 10
        resp["_view_seq"] = 11

        metrics = SessionMetrics(pending_timeout_seconds=1.0)
        first = metrics.process(req)
        second = metrics.process(resp)

        self.assertEqual(first["pending"], 1)
        self.assertEqual(second["pending"], 0)
        self.assertEqual(second["matched_request"]["seq"], 10)
        self.assertAlmostEqual(second["response_ms"], 125.0, places=6)

    def test_timeout_regression(self):
        req = parse_burst(
            append_crc(bytes.fromhex("05 04 00 00 00 01")),
            "12:00:00.000",
            "BUS",
            10.0,
        )[0]
        req["_view_seq"] = 77
        metrics = SessionMetrics(pending_timeout_seconds=1.0)
        metrics.process(req)
        self.assertEqual(metrics.expire_pending(11.1), 1)
        expired = metrics.pop_expired_requests()
        self.assertEqual(expired[0]["seq"], 77)
        self.assertEqual(metrics.timeouts, 1)


class SlaveFinderRegressionTests(unittest.TestCase):
    def test_normal_discovery_response(self):
        response = append_crc(bytes.fromhex("04 03 02 12 34"))
        found = find_discovery_response(response, 4, 3)
        self.assertIsNotNone(found)
        self.assertEqual(found["kind"], "RESPONSE")

    def test_discovery_exception_counts_as_response(self):
        response = append_crc(bytes.fromhex("04 83 02"))
        found = find_discovery_response(response, 4, 3)
        self.assertIsNotNone(found)
        self.assertEqual(found["kind"], "EXCEPTION")
        self.assertEqual(found["exception_code"], 2)

    def test_device_identification_request(self):
        request = build_device_identification_probe(4)
        self.assertEqual(request[:5], bytes.fromhex("04 2B 0E 01 00"))
        self.assertEqual(len(request), 7)
        self.assertTrue(crc_ok(request))

    def test_device_identification_response_parser(self):
        response = device_id_response(slave=4)
        found = find_device_identification_response(response, 4)
        self.assertIsNotNone(found)
        self.assertEqual(found["kind"], "DEVICE_ID")
        self.assertEqual(found["objects"][0x00], "Schneider Electric")
        self.assertEqual(found["objects"][0x01], "TEST-PRODUCT")
        self.assertEqual(found["objects"][0x02], "1.2.3")
        self.assertEqual(
            format_device_identification(found),
            "Schneider Electric | TEST-PRODUCT | 1.2.3",
        )

    def test_device_identification_parser_ignores_request_echo(self):
        request = build_device_identification_probe(4)
        response = device_id_response(slave=4)
        found = find_device_identification_response(request + response, 4)
        self.assertIsNotNone(found)
        self.assertEqual(found["objects"][0x01], "TEST-PRODUCT")

    def test_device_identification_exception(self):
        response = append_crc(bytes.fromhex("04 AB 01"))
        found = find_device_identification_response(response, 4)
        self.assertIsNotNone(found)
        self.assertEqual(found["kind"], "EXCEPTION")
        self.assertEqual(found["exception_code"], 1)
        self.assertIn("Illegal Function", format_device_identification(found))

    def test_device_identification_rejects_bad_crc(self):
        response = with_bad_crc(device_id_response(slave=4))
        self.assertIsNone(find_device_identification_response(response, 4))

    def test_device_identification_follows_more_follows(self):
        page0 = device_id_response(
            slave=4,
            objects={0x00: b"Vendor"},
            more_follows=True,
            next_object_id=0x01,
        )
        page1 = device_id_response(
            slave=4,
            objects={0x01: b"Product", 0x02: b"2.0"},
            more_follows=False,
            next_object_id=0x00,
        )
        serial = FakeSerial({0x00: page0, 0x01: page1})
        result = read_basic_device_identification(
            serial,
            4,
            115200,
            "None",
            "1",
            10,
            threading.Event(),
            FakeSerialModule,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["objects"][0x00], "Vendor")
        self.assertEqual(result["objects"][0x01], "Product")
        self.assertEqual(result["objects"][0x02], "2.0")
        self.assertEqual(len(serial.writes), 2)
        self.assertEqual(serial.writes[0][4], 0x00)
        self.assertEqual(serial.writes[1][4], 0x01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
