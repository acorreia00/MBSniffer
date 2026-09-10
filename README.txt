MBSNIFFER v2.9
================

MBSniffer é uma ferramenta Windows para diagnóstico de Modbus RTU.

- Sniffer: passivo; não transmite dados.
- Bus Slave Finder: ativo; transmite pedidos Modbus RTU de leitura.

NOVIDADES v2.9
--------------
- Frame Inspector estruturado e recolhível.
- Bus Health com métricas de qualidade/desempenho.
- Filtros avançados de Tráfego.
- Opção "Realçar resultados".
- Menu de contexto por frame.
- Indicador BUS RX.
- Exportação da sessão para CSV.
- Simulação de diagnóstico com anomalias em todas as execuções; "Realçar resultados" controla apenas as cores.
- Correção de ressincronização do parser após bursts longos de ruído.
- Frame gap Auto alinhado com Modbus RTU: acima de 19200 bit/s usa t3.5 fixo de 1,750 ms.
- Device Identification (FC43/14) opcional no Bus Slave Finder.
- Tema/layout Light/Dark da v2.8 mantido.

TRÁFEGO E FILTROS
-----------------
O separador Tráfego apresenta:

    Hora | Δt | Resp. | COM | Tipo | Slave | FC | Detalhes | CRC

Filtros disponíveis:

- Slave, através do cabeçalho "Slave";
- Tipo: Requests, Responses, Exceptions, CRC errors, Timeouts ou RAW;
- FC em hexadecimal;
- tempo de resposta acima de X ms;
- pesquisa livre em Details, Raw, Slave, FC, Tipo e COM/canal.

"Limpar filtros" repõe todos os filtros de Tráfego.

REALÇAR RESULTADOS
-----------------
A opção vem desligada por defeito. Quando ativa, os resultados recebem cor:

- CRC error;
- Timeout;
- Modbus Exception;
- resposta lenta (>= 500 ms);
- RAW/UNSYNC — bytes anteriores a um ponto onde o parser conseguiu recuperar sincronismo;
- RAW/UNPARSED — bytes restantes quando não foi possível encontrar um frame Modbus válido;
- transação normal concluída com sucesso — verde.

Numa transação normal concluída com sucesso, o REQUEST e a RESPONSE correspondente
ficam verdes. Requests pendentes continuam neutros. Respostas lentas mantêm a cor
de resposta lenta para que o resultado de diagnóstico não seja escondido.

Se debug_sim=1, "Simulação" gera sempre uma demonstração com resposta normal,
resposta lenta, Exception, CRC error, Timeout e RAW. "Realçar resultados" altera
apenas as cores dessas mesmas linhas, permitindo comparar diretamente a tabela
com o destaque desligado e ligado.


CÓDIGO DE CORES
---------------
Com "Realçar resultados" ativo:

- Verde — transação normal concluída com sucesso;
- Amarelo — resposta lenta (>= 500 ms);
- Vermelho — CRC Error ou Modbus Exception;
- Laranja — Timeout;
- Roxo — RAW/UNSYNC ou RAW/UNPARSED.

O Frame Inspector apresenta sempre a classificação no campo "Resultado", por
exemplo "Resultado: ✓ Sucesso". Com o destaque desligado o texto fica neutro;
com o destaque ligado o próprio campo usa a cor correspondente. O nome das
cores por extenso fica documentado apenas em Ajuda / Ligações.

FRAME INSPECTOR
---------------
Ao selecionar um frame, o painel inferior apresenta:

- Slave;
- Tipo;
- Function Code + nome;
- PDU Address;
- endereço 1-based;
- Qty;
- ByteCount;
- tempo de resposta;
- Resultado;
- CRC recebido;
- CRC calculado;
- dados / registos / Exception;
- Raw Hex.

O painel pode ser "Recolher" / "Expandir" para libertar espaço para Tráfego.

MENU DE CONTEXTO
----------------
Botão direito numa frame:

- Copiar Raw Hex;
- Copiar frame descodificado;
- Filtrar por este Slave;
- Filtrar por este FC;
- Mostrar apenas esta transação;
- Limpar filtro de transação.

BUS HEALTH
----------
O separador Bus Health inclui:

- Requests e Responses;
- Request rate;
- Slaves ativos;
- bytes observados;
- utilização aproximada do bus;
- response time médio, mínimo, máximo e P95;
- Slave mais lento;
- percentagem de bytes não validados;
- timeout rate;
- Exceptions por Slave.

A percentagem de bytes não validados é calculada sobre os bytes observados que
pertencem a frames com CRC inválido ou a blocos RAW. É um indicador de captura
não validada, não uma prova isolada de ruído/EMI. Parâmetros série errados, uma
captura incompleta ou funções não suportadas pelo parser também podem gerar RAW.

A utilização do barramento é uma estimativa baseada nos bytes observados e nos
parâmetros série configurados. Não substitui um osciloscópio/analisador lógico.

O Bus Health adapta automaticamente a disposição das métricas à altura disponível. Com menos espaço vertical, as métricas reorganizam-se em duas colunas dentro de cada retângulo; quando volta a existir espaço, regressam ao formato vertical normal. Assim nenhuma linha fica por cima da borda inferior.


INDICADOR BUS
-------------
"BUS ● RX" pulsa brevemente quando o Sniffer recebe tráfego.
Em repouso mostra "BUS ○".

EXPORTAR CSV
------------
"Exportar CSV" grava os frames atualmente retidos pela interface, incluindo:

    Time, Delta ms, Response ms, Channel, Type, Slave, FC, Details, CRC,
    Raw, PDU Address, 1-based Address, Qty, Byte Count, Timed out, Anomaly

A interface mantém no máximo 20 000 frames para preservar desempenho.
O log TXT de uma captura real continua a ser o registo completo em disco.

PARSER / RESSINCRONIZAÇÃO
-------------------------
Quando perde sincronismo, o parser procura no restante burst o próximo frame
Modbus com estrutura reconhecida e CRC válido. A pesquisa percorre todo o burst,
mas deixa de testar por força bruta centenas de comprimentos em cada posição.
Assim recupera frames válidos após ruído longo sem bloquear a receção durante
vários segundos.

Se os bytes imediatamente anteriores ao ponto recuperado tiverem exatamente a
estrutura de um frame Modbus conhecido mas CRC inválido, são classificados como
CRC ERROR. Ruído sem uma estrutura de frame reconhecível continua como RAW.

Durante a ressincronização não são aceites frames apenas por coincidência de CRC.
Isto reduz fortemente falsos frames ocasionais em sequências de ruído aleatório.

FRAME GAP AUTO
--------------
Em modo Auto, o Sniffer calcula t3.5 a partir de 3,5 tempos de carácter até
19200 bit/s, inclusive. Acima de 19200 bit/s utiliza o valor fixo recomendado
de 1,750 ms. O modo Manual não é alterado.

BUS SLAVE FINDER / DEVICE IDENTIFICATION
----------------------------------------
O Bus Slave Finder continua a localizar Slaves através de FC03 e, opcionalmente,
FC04 fallback.

A opção "Device Identification (FC43/14)" vem desligada por defeito. Quando
ativada, é enviada apenas depois de um Slave já ter sido encontrado. O Finder
tenta ler Basic Device Identification e apresenta, quando disponíveis:

    VendorName | ProductCode | MajorMinorRevision

Se FC43/14 não for suportado, devolver uma Modbus Exception ou não responder a
essa função não invalida o Slave que já tinha sido encontrado.

MODO CLARO / ESCURO
-----------------
O seletor global fica no canto superior direito.

Os modos claro e escuro usam exatamente a mesma construção da interface; mudar o seletor
altera apenas cores. A escolha fica guardada automaticamente.

PREFERÊNCIAS GUARDADAS
----------------------
Ficheiro único:

    %APPDATA%\MBSniffer\settings.json

São guardados:

- modo claro/escuro;
- último separador principal;
- modo físico;
- Baud, Data bits, Parity e Stop bits;
- Frame gap Auto/Manual e Gap manual;
- Pending timeout;
- deslocamento automático;
- Separar transações;
- Realçar resultados;
- opções do Bus Slave Finder, incluindo FC04 fallback e Device Identification.

Não são guardados:

- COM A / COM B / COM do Bus Slave Finder;
- confirmação de segurança do Bus Slave Finder;
- tamanho/posição da janela;
- tráfego, estatísticas ou resultados.

EXECUTAR
--------
Depois de extrair o ZIP:

    MBSniffer.bat

O BAT verifica/instala automaticamente o pyserial.

BUILD DO EXE
------------
Executar:

    MBSniffer v2.9\build_exe.bat

Antes do build, os testes de regressão são executados automaticamente. Se algum teste falhar, o build é cancelado.

O resultado é criado diretamente na raiz:

    MBSniffer.exe

TESTES DE REGRESSÃO
-------------------
Podem ser executados manualmente através de:

    MBSniffer v2.9\run_tests.bat

A suite verifica CRC, parser/ressincronização, Function Codes suportados, pairing, timeouts, frame gap Auto, Bus Slave Finder e Device Identification FC43/14.

LOGS
----
Capturas reais só criam um ficheiro quando existe tráfego.

Pasta:

    MBSniffer Logs\

fica ao lado de MBSniffer.bat / MBSniffer.exe.

REQUISITOS
----------
Windows 10/11 x64.
Python 3.10+ quando executado através do BAT/Python.

BARRAS DE DESLOCAMENTO
----------
As barras de deslocamento usam um desenho minimalista de 6 px, sem botões de seta. A pista
tem a mesma cor do fundo do conteúdo e fica visualmente invisível; apenas o
cursor móvel fica aparente.

A roda do rato só atua quando o ponteiro está sobre uma barra de deslocamento. Fora das
barras de deslocamento não desloca Text/Treeview nem muda de separador do programa.
