
# ==========================================================
# BIBLIOTECAS E MODULOS
# ==========================================================

# machine: permite acessar os recursos físicos da ESP32.
import machine
import micropython

# Reserva um pequeno buffer para facilitar o diagnóstico de exceções
# relacionadas ao tratamento de interrupções.
micropython.alloc_emergency_exception_buf(100)

# network: disponibiliza os recursos de conexão Wi-Fi.
import network

# time: utilizado para controlar intervalos sem sleep.
import time

# dht: biblioteca responsável pela leitura do DHT22.
import dht

# ujson: converte estruturas Python para JSON.
import ujson

# urequests: realiza requisições HTTP e HTTPS.
import urequests

# Importa componentes do módulo machine.
from machine import Pin, ADC, I2C, Timer

# Importa o driver do BMP280.
from bmp280 import BMP280


# ==========================================================
# CONFIGURACOES GERAIS DO PROJETO
# ==========================================================

# Credenciais de wifi
WIFI_SSID = "WIFI"
WIFI_PASSWORD = "SENHA"


# Endereço da API hospedada no Render.
API_URL = "https://estacao-meteorologica-api.onrender.com/dados"


# Intervalo entre os envios para a API.
INTERVALO_ENVIO = 1000


# Intervalo entre as leituras do DHT22.
INTERVALO_DHT = 2000


# Quantidade de leituras utilizadas na média do MQ-135.
# Isso garante maior estabilidade do sensor.
QUANTIDADE_LEITURAS_MQ = 20


# ==========================================================
# CONFIGURACOES DAS INTERRUPCOES DE TEMPORIZADOR
# ==========================================================

# Flags pré-alocadas compartilhadas com as interrupções.
# Os callbacks apenas sinalizam os eventos.
# O processamento será realizado no loop principal.

evento_dht = bytearray(1)
evento_envio = bytearray(1)


# ==========================================================
# CONFIGURACOES DA RECONEXAO WI-FI
# ==========================================================

# Tempo máximo permitido para cada tentativa de conexão.
TEMPO_LIMITE_CONEXAO = 15000


# Intervalo de espera entre tentativas de reconexão.
INTERVALO_RECONEXAO = 5000


# Controla se existe uma tentativa de conexão em andamento.
tentativa_conexao_ativa = False


# Armazena o instante em que a tentativa atual começou.
inicio_tentativa_conexao = 0


# Armazena o instante da última tentativa de conexão.
ultima_tentativa_conexao = None


# Indica se a conexão já foi estabelecida anteriormente.
wifi_conectado_anteriormente = False


# Evita repetir mensagens de ausência de conexão
# a cada ciclo de envio.
aviso_sem_wifi = False


# ==========================================================
# INICIALIZACAO DOS SENSORES
# ==========================================================

# ----------------------------------------------------------
# DHT22 - TEMPERATURA E UMIDADE
# ----------------------------------------------------------

# Inicializa o DHT22 no GPIO 4.
dht_sensor = dht.DHT22(Pin(4))


# Armazena a última leitura válida do DHT22.
temperatura_dht = None
umidade_dht = None


# ----------------------------------------------------------
# BMP280 - PRESSAO ATMOSFERICA
# ----------------------------------------------------------

# Configura a comunicação I2C.
i2c = I2C(
    0,
    scl=Pin(22),
    sda=Pin(21),
    freq=100000
)


# Inicializa o BMP280 no endereço 0x76.
bmp_sensor = BMP280(i2c, addr=0x76)


# ----------------------------------------------------------
# LDR - SENSOR DE LUMINOSIDADE COM INTERRUPCAO
# ----------------------------------------------------------

# O GPIO 34 é uma entrada digital e pode detectar interrupções
# externas. Ele não possui pull-up/pull-down interno, portanto
# o pino deve continuar recebendo um sinal definido pela saída DO.
ldr_sensor = Pin(34, Pin.IN)


# Tempo mínimo sem novas transições para considerar o estado estável.
# Ajuda a ignorar pequenas oscilações do comparador do módulo LDR.
TEMPO_ESTABILIZACAO_LDR = 50


# Flag pré-alocada compartilhada com o callback da interrupção.
# O callback apenas altera essa flag; não imprime nem lê outros sensores.
ldr_interrupcao_pendente = bytearray(1)


# Estado inicial conhecido do LDR (1 = escuro; 0 = claro, conforme os testes).
estado_ldr_estavel = ldr_sensor.value()


# Controle da verificação de estabilidade, executada no loop principal.
verificacao_ldr_ativa = False
inicio_verificacao_ldr = 0


def interrupcao_ldr(pin):

    # Rotina curta: apenas sinaliza que ocorreu uma transição no pino.
    ldr_interrupcao_pendente[0] = 1


# Detecta tanto a transição claro -> escuro quanto escuro -> claro.
ldr_sensor.irq(
    trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
    handler=interrupcao_ldr
)


def processar_evento_ldr():

    global verificacao_ldr_ativa
    global inicio_verificacao_ldr
    global estado_ldr_estavel

    # Acessa a flag por uma seção crítica muito curta para evitar
    # perder uma sinalização enquanto o loop principal a limpa.
    estado_interrupcao = machine.disable_irq()
    evento_detectado = ldr_interrupcao_pendente[0]
    ldr_interrupcao_pendente[0] = 0
    machine.enable_irq(estado_interrupcao)

    # Cada nova transição reinicia a janela de estabilização.
    if evento_detectado:
        verificacao_ldr_ativa = True
        inicio_verificacao_ldr = time.ticks_ms()

    # Só confirma o novo estado após 50 ms sem nova transição.
    if verificacao_ldr_ativa:

        agora = time.ticks_ms()

        if time.ticks_diff(agora, inicio_verificacao_ldr) >= TEMPO_ESTABILIZACAO_LDR:

            novo_estado = ldr_sensor.value()

            if novo_estado != estado_ldr_estavel:

                estado_ldr_estavel = novo_estado

                if novo_estado == 1:
                    print("Interrupção LDR: ambiente escuro (DO=1).")
                else:
                    print("Interrupção LDR: ambiente claro (DO=0).")

            verificacao_ldr_ativa = False


if estado_ldr_estavel == 1:
    print("Estado inicial do LDR: ESCURO (DO=1).")
else:
    print("Estado inicial do LDR: CLARO (DO=0).")

print("Interrupção do LDR configurada nas duas bordas do GPIO 34.")


# ----------------------------------------------------------
# MQ-135 - QUALIDADE DO AR
# ----------------------------------------------------------

# Inicializa o ADC no GPIO 35.
adc_mq135 = ADC(Pin(35))

# Configura a atenuação do ADC.
adc_mq135.atten(ADC.ATTN_11DB)


# ==========================================================
# INTERRUPCOES DOS TEMPORIZADORES
# ==========================================================

# ----------------------------------------------------------
# TIMER 0 - INTERRUPCAO DO DHT22
# ----------------------------------------------------------

def interrupcao_timer_dht(timer):

    # Apenas sinaliza que chegou o momento da leitura.
    # A leitura real será realizada no loop principal.
    evento_dht[0] = 1


# ----------------------------------------------------------
# TIMER 1 - INTERRUPCAO DO ENVIO PARA A API
# ----------------------------------------------------------

def interrupcao_timer_envio(timer):

    # Apenas sinaliza que chegou o momento do envio.
    # A coleta e o envio serão realizados no loop principal.
    evento_envio[0] = 1


# ----------------------------------------------------------
# INICIALIZACAO DOS TEMPORIZADORES
# ----------------------------------------------------------

# Cria os objetos dos temporizadores.
timer_dht = Timer(0)
timer_envio = Timer(1)


def iniciar_temporizadores():

    # Configura o Timer 0 para gerar uma interrupção
    # periódica a cada 2000 milissegundos.
    timer_dht.init(
        mode=Timer.PERIODIC,
        period=INTERVALO_DHT,
        callback=interrupcao_timer_dht
    )

    # Configura o Timer 1 para gerar uma interrupção
    # periódica a cada 1000 milissegundos.
    timer_envio.init(
        mode=Timer.PERIODIC,
        period=INTERVALO_ENVIO,
        callback=interrupcao_timer_envio
    )

    print("Interrupção do DHT22 configurada: 2000 ms.")
    print("Interrupção de envio configurada: 1000 ms.")


# ----------------------------------------------------------
# PROCESSAMENTO DOS EVENTOS DOS TEMPORIZADORES
# ----------------------------------------------------------

def verificar_eventos_timer():

    # Desabilita temporariamente as interrupções para acessar
    # e limpar as flags sem perder sinalizações.
    estado_irq = machine.disable_irq()

    # Captura os eventos sinalizados pelos temporizadores.
    leitura_dht_pendente = evento_dht[0]
    envio_pendente = evento_envio[0]

    # Limpa as flags após a captura.
    evento_dht[0] = 0
    evento_envio[0] = 0

    # Restaura o estado anterior das interrupções.
    machine.enable_irq(estado_irq)

    return leitura_dht_pendente, envio_pendente


# ==========================================================
# CLASSIFICACAO DA QUALIDADE DO AR
# ==========================================================

# Classificação experimental baseada nos testes realizados com mq-135

# Não representa PPM

def classificar_qualidade_ar(valor):

    if valor <= 410:
        return "EXCELENTE"

    elif valor <= 450:
        return "BOA"

    elif valor <= 550:
        return "MODERADA"

    elif valor <= 700:
        return "RUIM"

    else:
        return "PESSIMA"


# ==========================================================
# LEITURA DO SENSOR MQ-135
# ==========================================================

def ler_mq135():

    soma = 0

    # Realiza várias leituras analógicas.
    for _ in range(QUANTIDADE_LEITURAS_MQ):

        soma += adc_mq135.read()

    # Calcula a média das amostras.
    media = soma / QUANTIDADE_LEITURAS_MQ

    # Classifica o resultado médio.
    qualidade = classificar_qualidade_ar(media)

    return media, qualidade


# ==========================================================
# LEITURA DO DHT22
# ==========================================================

# Atualiza independentemente temperatura e umidade.
# Em caso de erro, mantém a última leitura válida.

def atualizar_dht():

    global temperatura_dht, umidade_dht

    try:

        dht_sensor.measure()

        temperatura_dht = dht_sensor.temperature()

        umidade_dht = dht_sensor.humidity()

        print("Nova leitura do DHT22 realizada.")

    except Exception as erro:

        print("Erro na leitura do DHT22:", erro)


# ==========================================================
# INICIALIZACAO DO WI-FI
# ==========================================================

# Cria a interface de rede no modo estação.
wifi = network.WLAN(network.STA_IF)


# Ativa a interface Wi-Fi.
#
# A conexão propriamente dita será controlada
# posteriormente pelo loop principal.
def inicializar_wifi():

    wifi.active(True)

    print("Interface Wi-Fi ativada.")
    print("Aguardando conexão com a rede...")


# ==========================================================
# CONTROLE NAO BLOQUEANTE DA CONEXAO WI-FI
# ==========================================================

# Verifica o estado da conexão e inicia tentativas
# de reconexão sem interromper o loop principal.

def verificar_wifi():

    global tentativa_conexao_ativa
    global inicio_tentativa_conexao
    global ultima_tentativa_conexao
    global wifi_conectado_anteriormente
    global aviso_sem_wifi

    agora = time.ticks_ms()


    # ------------------------------------------------------
    # 1. VERIFICA SE O WI-FI ESTA CONECTADO
    # ------------------------------------------------------

    if wifi.isconnected():

        # Exibe a mensagem somente quando a conexão
        # é estabelecida ou restabelecida.
        if not wifi_conectado_anteriormente:

            print("Wi-Fi conectado!")
            print("IP:", wifi.ifconfig()[0])

        wifi_conectado_anteriormente = True

        tentativa_conexao_ativa = False

        # Libera a mensagem de ausência de conexão.
        aviso_sem_wifi = False

        return True


    # ------------------------------------------------------
    # IDENTIFICA A DESCONEXAO
    # ------------------------------------------------------

    if wifi_conectado_anteriormente:

        print("Wi-Fi desconectado.")
        print("Iniciando processo de reconexão...")

    wifi_conectado_anteriormente = False


    # ------------------------------------------------------
    # VERIFICA UMA TENTATIVA EM ANDAMENTO
    # ------------------------------------------------------

    if tentativa_conexao_ativa:

        # Verifica se a tentativa ultrapassou o limite de 15 s.
        tempo_tentativa = time.ticks_diff(
            agora,
            inicio_tentativa_conexao
        )

        if tempo_tentativa >= TEMPO_LIMITE_CONEXAO:

            print("Tempo limite de conexão atingido.")
            print("Uma nova tentativa será realizada.")

            # Encerra a tentativa atual.
            tentativa_conexao_ativa = False

            # Registra o horário para controlar a próxima tentativa.
            ultima_tentativa_conexao = agora

            # Cancela uma possível tentativa que ficou pendente.
            try:

                wifi.disconnect()

            except Exception as erro:

                print("Aviso ao cancelar conexão:", erro)

        # Retorna sem bloquear o programa.
        return False


    # ------------------------------------------------------
    # VERIFICA SE JA PODE INICIAR OUTRA TENTATIVA
    # ------------------------------------------------------

    pode_tentar = (

        ultima_tentativa_conexao is None

        or time.ticks_diff(
            agora,
            ultima_tentativa_conexao
        ) >= INTERVALO_RECONEXAO

    )

    if not pode_tentar:
        return False


    # ------------------------------------------------------
    # INICIA UMA NOVA TENTATIVA DE CONEXAO
    # ------------------------------------------------------

    print("Tentando conectar ao Wi-Fi...")

    try:

        # Solicita conexão com a rede configurada.
        wifi.connect(
            WIFI_SSID,
            WIFI_PASSWORD
        )

        # Registra o início da tentativa.
        inicio_tentativa_conexao = agora

        ultima_tentativa_conexao = agora

        tentativa_conexao_ativa = True

    except Exception as erro:

        print("Erro ao iniciar conexão Wi-Fi:", erro)

        # Registra a tentativa para evitar chamadas
        # repetidas em sequência.
        ultima_tentativa_conexao = agora

    return False


# ==========================================================
# LEITURA DE TODOS OS SENSORES
# ==========================================================

# Reúne as últimas medições disponíveis.
#
# O DHT22 utiliza os valores armazenados pela atualizar_dht().
# O LDR utiliza o último estado confirmado pelo tratamento da interrupção.
# BMP280 e MQ-135 são consultados neste ciclo de envio.

def ler_sensores():

    print("\nLendo sensores...")

    # ------------------------------------------------------
    # DHT22
    # ------------------------------------------------------

    temperatura = temperatura_dht
    umidade = umidade_dht


    # ------------------------------------------------------
    # BMP280 - PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    # O driver retorna Pascal (Pa).
    # A divisão por 100 converte para hPa.
    pressao = bmp_sensor.pressure / 100


    # ------------------------------------------------------
    # LDR - LUMINOSIDADE DIGITAL
    # ------------------------------------------------------

    # Utiliza o último estado confirmado pela interrupção e pela
    # verificação de estabilidade no loop principal.
    luminosidade = estado_ldr_estavel


    # ------------------------------------------------------
    # MQ-135 - QUALIDADE DO AR
    # ------------------------------------------------------

    adc_mq135, qualidade_ar = ler_mq135()


    # ------------------------------------------------------
    # EXIBICAO NO MONITOR SERIAL
    # ------------------------------------------------------

    print("--------------------------------")
    print("Temperatura:", temperatura, "C")
    print("Umidade:", umidade, "%")
    print("Pressao:", round(pressao, 2), "hPa")
    print("Luminosidade (DO):", luminosidade)
    print("ADC MQ-135:", round(adc_mq135, 2))
    print("Qualidade do ar:", qualidade_ar)
    print("--------------------------------")


    # ------------------------------------------------------
    # ORGANIZACAO DOS DADOS PARA A API
    # ------------------------------------------------------

    dados = {
        "temperatura": temperatura,
        "umidade": umidade,
        "pressao": pressao,
        "luminosidade": luminosidade,
        "adc_mq135": adc_mq135,
        "qualidade_ar": qualidade_ar
    }

    return dados


# ==========================================================
# ENVIO DOS DADOS PARA A API
# ==========================================================

def enviar_api(dados):

    try:

        # Envia os dados em formato JSON.
        resposta = urequests.post(
            API_URL,
            data=ujson.dumps(dados),
            headers={
                "Content-Type": "application/json"
            }
        )

        # Apresenta o código HTTP recebido.
        print("Resposta da API:", resposta.status_code)

        # Exibe a mensagem quando ocorre uma resposta diferente de 200.
        if resposta.status_code != 200:

            print("Mensagem da API:", resposta.text)

        # Fecha a resposta para liberar os recursos.
        resposta.close()

    except Exception as erro:

        print("Erro ao enviar dados:", erro)


# ==========================================================
# INICIALIZACAO DO PROJETO
# ==========================================================

print("================================")
print(" ESTACAO METEOROLOGICA ESP32")
print("================================")


# ----------------------------------------------------------
# ATIVACAO DO WI-FI
# ----------------------------------------------------------

# Apenas ativa a interface.
# A conexão será controlada pelo loop principal.
inicializar_wifi()


# ----------------------------------------------------------
# PRIMEIRA LEITURA DO DHT22
# ----------------------------------------------------------

# Realiza a primeira leitura antes dos envios.
atualizar_dht()


# ----------------------------------------------------------
# INICIALIZACAO DAS INTERRUPCOES DE TEMPORIZADOR
# ----------------------------------------------------------

# Inicia os temporizadores responsáveis por sinalizar
# os eventos periódicos do DHT22 e do envio para a API.
iniciar_temporizadores()


# ==========================================================
# LOOP PRINCIPAL
# ==========================================================

while True:

    # ------------------------------------------------------
    # 0. PROCESSAMENTO DO EVENTO DO LDR
    # ------------------------------------------------------

    # A interrupção apenas sinaliza a mudança. A confirmação do
    # estado é executada aqui, fora do callback, com debounce.
    processar_evento_ldr()


    # ------------------------------------------------------
    # 1. VERIFICACAO DO WI-FI
    # ------------------------------------------------------

    # Verifica a conexão e inicia novas tentativas quando
    # necessário, sem interromper a execução do programa.
    verificar_wifi()


    # ------------------------------------------------------
    # 2. VERIFICACAO DOS EVENTOS DOS TEMPORIZADORES
    # ------------------------------------------------------

    # Captura os eventos sinalizados pelas interrupções.
    # As flags são limpas dentro de uma seção crítica.
    leitura_dht_pendente, envio_pendente = verificar_eventos_timer()


    # ------------------------------------------------------
    # 3. CONTROLE INDEPENDENTE DO DHT22
    # ------------------------------------------------------

    if leitura_dht_pendente:

        # Realiza uma nova leitura fora da interrupção.
        atualizar_dht()


    # ------------------------------------------------------
    # 4. CONTROLE DO INTERVALO DE ENVIO
    # ------------------------------------------------------

    if envio_pendente:


        # --------------------------------------------------
        # 5. VERIFICAR SE EXISTE UMA LEITURA VALIDA DO DHT22
        # --------------------------------------------------

        if temperatura_dht is None or umidade_dht is None:

            print("Aguardando uma leitura válida do DHT22.")

        else:

            try:

                # A coleta continua acontecendo mesmo quando
                # a ESP32 está temporariamente sem Wi-Fi.
                dados = ler_sensores()


                # --------------------------------------------------
                # 6. VERIFICAR SE OS DADOS PODEM SER ENVIADOS
                # --------------------------------------------------

                if wifi.isconnected():

                    enviar_api(dados)

                else:

                    # Evita repetir esta mensagem a cada ciclo de envio.
                    if not aviso_sem_wifi:

                        print(
                            "Sem Wi-Fi. As leituras continuam, "
                            "mas esta medição não será enviada."
                        )

                        aviso_sem_wifi = True

            except Exception as erro:

                print("Erro na leitura dos sensores:", erro)


    # ------------------------------------------------------
    # 7. AGUARDAR EVENTOS
    # ------------------------------------------------------

    # Permite que a ESP32 aguarde eventos do sistema
    # sem bloquear a lógica de reconexão.
    machine.idle()

