
# ==========================================================
# BIBLIOTECAS E MODULOS
# ==========================================================

# machine: permite acessar os recursos físicos da ESP32.
import machine

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
from machine import Pin, ADC, I2C

# Importa o driver do BMP280.
from bmp280 import BMP280


# ==========================================================
# CONFIGURACOES GERAIS DO PROJETO
# ==========================================================

# Credenciais de wifi
WIFI_SSID = "wifi"
WIFI_PASSWORD = "senha"


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
# LDR - SENSOR DE LUMINOSIDADE
# ----------------------------------------------------------

# Configura GPIO 34 como entrada digital.
ldr_sensor = Pin(34, Pin.IN)


# ----------------------------------------------------------
# MQ-135 - QUALIDADE DO AR
# ----------------------------------------------------------

# Inicializa o ADC no GPIO 35.
adc_mq135 = ADC(Pin(35))

# Configura a atenuação do ADC.
adc_mq135.atten(ADC.ATTN_11DB)


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
# Os outros sensores são consultados neste ciclo.

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

    luminosidade = ldr_sensor.value()


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


# Registra os instantes iniciais dos intervalos.
ultima_leitura_dht = time.ticks_ms()

ultimo_envio = time.ticks_ms()


# ==========================================================
# LOOP PRINCIPAL
# ==========================================================

while True:

    # ------------------------------------------------------
    # 1. VERIFICACAO DO WI-FI
    # ------------------------------------------------------

    # Verifica a conexão e inicia novas tentativas quando
    # necessário, sem interromper a execução do programa.
    verificar_wifi()


    # Obtém o instante atual.
    agora = time.ticks_ms()


    # ------------------------------------------------------
    # 2. CONTROLE INDEPENDENTE DO DHT22
    # ------------------------------------------------------

    if time.ticks_diff(
        agora,
        ultima_leitura_dht
    ) >= INTERVALO_DHT:

        # Realiza uma nova leitura.
        atualizar_dht()

        # Registra o instante da última tentativa.
        ultima_leitura_dht = time.ticks_ms()


    # Atualiza o instante após a possível leitura do DHT22.
    agora = time.ticks_ms()


    # ------------------------------------------------------
    # 3. CONTROLE DO INTERVALO DE ENVIO
    # ------------------------------------------------------

    if time.ticks_diff(
        agora,
        ultimo_envio
    ) >= INTERVALO_ENVIO:

        ultimo_envio = agora


        # --------------------------------------------------
        # 4. VERIFICAR SE EXISTE UMA LEITURA VALIDA DO DHT22
        # --------------------------------------------------

        if temperatura_dht is None or umidade_dht is None:

            print("Aguardando uma leitura válida do DHT22.")

        else:

            try:

                # A coleta continua acontecendo mesmo quando
                # a ESP32 está temporariamente sem Wi-Fi.
                dados = ler_sensores()


                # --------------------------------------------------
                # 5. VERIFICAR SE OS DADOS PODEM SER ENVIADOS
                # --------------------------------------------------

                if wifi.isconnected():

                    enviar_api(dados)

                else:

                    # Evita repetir esta mensagem a cada segundo.
                    if not aviso_sem_wifi:

                        print(
                            "Sem Wi-Fi. As leituras continuam, "
                            "mas esta medição não será enviada."
                        )

                        aviso_sem_wifi = True

            except Exception as erro:

                print("Erro na leitura dos sensores:", erro)


    # ------------------------------------------------------
    # 6. AGUARDAR EVENTOS
    # ------------------------------------------------------

    # Permite que a ESP32 aguarde eventos do sistema
    # sem bloquear a lógica de reconexão.
    machine.idle()

