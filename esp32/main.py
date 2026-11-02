# ==========================================================
# BIBLIOTECAS E MODULOS
# ==========================================================

# machine: permite acessar os recursos físicos da ESP32,
# como pinos, conversores analógico-digitais e comunicação I2C.
import machine

# network: disponibiliza os recursos de conexão de rede,
# permitindo conectar a ESP32 a uma rede Wi-Fi.
import network

# time: fornece funções para medir intervalos de tempo.
# Neste projeto, é utilizado para controlar o momento dos envios
# sem recorrer a time.sleep() ou time.sleep_ms().
import time

# dht: biblioteca utilizada para realizar a leitura
# dos sensores da família DHT, neste projeto, o DHT22.
import dht

# ujson: permite converter estruturas de dados Python
# para o formato JSON, utilizado na comunicação com a API.
import ujson

# urequests: permite realizar requisições HTTP e HTTPS,
# possibilitando o envio dos dados coletados para a API.
import urequests


# Importa componentes específicos do módulo machine.
# Pin: configuração e leitura dos pinos digitais da ESP32.
# ADC: leitura de sinais analógicos.
# I2C: comunicação utilizada pelo sensor BMP280.
from machine import Pin, ADC, I2C

# Importa a classe BMP280 do arquivo bmp280.py.
# Esse arquivo contém as instruções necessárias para
# comunicação e leitura do sensor de pressão atmosférica.
from bmp280 import BMP280


# ==========================================================
# CONFIGURACOES GERAIS DO PROJETO
# ==========================================================

# Nome e senha da rede Wi-Fi que será utilizada pela ESP32.
# A conexão com a internet é necessária para enviar os dados
# coletados pelos sensores até a API hospedada no Render.

WIFI_SSID = "WIFI"
WIFI_PASSWORD = "SENHA"


# Endereço da API que receberá os dados da estação meteorológica.
# A rota /dados recebe as informações enviadas pela ESP32
# através de uma requisição HTTP do tipo POST.
API_URL = "https://estacao-meteorologica-api.onrender.com/dados"


# Intervalo utilizado pelo loop principal para iniciar um novo
# ciclo de leitura e envio dos dados.
# O valor é definido em milissegundos: 1000 ms = 1 segundo.
# O tempo real entre envios também depende da duração das leituras
# e da comunicação com a API.
INTERVALO_ENVIO = 1000


# Quantidade de amostras utilizadas para calcular a média
# das leituras do sensor MQ-135.
# A utilização de várias amostras ajuda a reduzir pequenas
# oscilações nas leituras, deixando o valor médio mais estável.
QUANTIDADE_LEITURAS_MQ = 20


# ==========================================================
# INICIALIZACAO DOS SENSORES
# ==========================================================

# ----------------------------------------------------------
# DHT22 - TEMPERATURA E UMIDADE
# ----------------------------------------------------------

# Inicializa o sensor DHT22 conectado ao pino GPIO 4 da ESP32.
# Esse sensor realiza duas medições:
# - Temperatura do ambiente, em graus Celsius.
# - Umidade relativa do ar, em porcentagem.
dht_sensor = dht.DHT22(Pin(4))


# ----------------------------------------------------------
# BMP280 - PRESSAO ATMOSFERICA
# ----------------------------------------------------------

# Inicializa a comunicação I2C da ESP32.
# I2C é um protocolo de comunicação que permite que a ESP32
# troque informações com dispositivos conectados por duas linhas:
#
# SDA: linha utilizada para transmitir e receber dados.
# SCL: linha responsável pelo sinal de clock.
#
# I2C(0): seleciona o controlador I2C de número 0.
# scl=Pin(22): define o GPIO 22 como linha de clock.
# sda=Pin(21): define o GPIO 21 como linha de dados.
# freq=100000: configura a comunicação em 100 kHz.
i2c = I2C(
    0,
    scl=Pin(22),
    sda=Pin(21),
    freq=100000
)


# Inicializa o BMP280 utilizando a comunicação I2C.
# addr=0x76: endereço I2C configurado para identificar
# o sensor na comunicação com a ESP32.
bmp_sensor = BMP280(i2c, addr=0x76)


# ----------------------------------------------------------
# LDR - SENSOR DE LUMINOSIDADE
# ----------------------------------------------------------

# Configura o pino GPIO 34 como entrada digital.
# O sensor LDR utilizado possui uma saída digital (DO).
# Por isso, a leitura informa apenas dois estados:
# 0: nível lógico baixo.
# 1: nível lógico alto.
# O valor depende do ajuste do potenciômetro do módulo.
# Essa leitura não representa diretamente a luminosidade em lux,
# pois não estamos utilizando a saída analógica (AO).
ldr_sensor = Pin(34, Pin.IN)


# ----------------------------------------------------------
# MQ-135 - SENSOR DE QUALIDADE DO AR
# ----------------------------------------------------------

# Inicializa o conversor analógico-digital (ADC) da ESP32
# utilizando o pino GPIO 35.
# O pino está conectado à saída analógica (AO) do MQ-135,
# por meio de um divisor de tensão.
adc_mq135 = ADC(Pin(35))


# Configura a atenuação do ADC.
# ATTN_11DB amplia a faixa de tensão que pode ser medida
# pelo conversor analógico-digital da ESP32.
adc_mq135.atten(ADC.ATTN_11DB)


# ==========================================================
# CLASSIFICACAO DA QUALIDADE DO AR
# ==========================================================

# Esta função recebe o valor médio ADC do MQ-135 e retorna
# uma classificação experimental da qualidade do ar.
# O valor ADC é comparado com faixas previamente definidas.
#
# IMPORTANTE: essas faixas foram estabelecidas com base no
# comportamento observado no sensor utilizado no projeto.
# Não representam um índice oficial de qualidade do ar,
# nem uma concentração de gases em PPM.
def classificar_qualidade_ar(valor):

    # Valores de até 410 recebem a classificação EXCELENTE.
    if valor <= 410:
        return "EXCELENTE"

    # Valores acima de 410 e até 450 recebem a classificação BOA.
    elif valor <= 450:
        return "BOA"

    # Valores acima de 450 e até 550 recebem a classificação MODERADA.
    elif valor <= 550:
        return "MODERADA"

    # Valores acima de 550 e até 700 recebem a classificação RUIM.
    elif valor <= 700:
        return "RUIM"

    # Valores acima de 700 recebem a classificação PESSIMA.
    else:
        return "PESSIMA"


# ==========================================================
# LEITURA DO SENSOR MQ-135
# ==========================================================

# Esta função realiza várias leituras do MQ-135, calcula a média
# e determina a classificação experimental da qualidade do ar.
# O objetivo é reduzir a influência de pequenas oscilações
# que podem ocorrer durante as medições do sensor.
def ler_mq135():

    # Inicializa a variável que armazenará a soma das leituras.
    soma = 0

    # Executa a leitura do ADC a quantidade de vezes definida
    # em QUANTIDADE_LEITURAS_MQ.
    # O caractere "_" é utilizado porque não precisamos guardar
    # o número de cada repetição.
    for _ in range(QUANTIDADE_LEITURAS_MQ):

        # Lê o valor analógico do MQ-135 e adiciona o resultado
        # à variável soma.
        soma += adc_mq135.read()

    # Divide a soma pela quantidade de leituras realizadas.
    # O resultado representa a média das amostras do sensor.
    media = soma / QUANTIDADE_LEITURAS_MQ

    # Envia a média para a função de classificação,
    # que retorna a categoria correspondente.
    qualidade = classificar_qualidade_ar(media)

    # Retorna duas informações para quem chamou a função:
    # 1. A média das leituras ADC.
    # 2. A classificação experimental da qualidade do ar.
    return media, qualidade


# ==========================================================
# CONEXAO COM A REDE WI-FI
# ==========================================================

# Cria a interface de rede da ESP32 no modo estação (STA).
# Nesse modo, a ESP32 funciona como um dispositivo cliente,
# conectando-se a uma rede Wi-Fi existente.
wifi = network.WLAN(network.STA_IF)


# Esta função ativa a interface Wi-Fi, verifica se já existe
# uma conexão e tenta conectar à rede configurada no início.
def conectar_wifi():

    # Ativa o módulo de comunicação Wi-Fi da ESP32.
    wifi.active(True)

    # Verifica se a ESP32 já está conectada.
    # Caso esteja, não é necessário realizar uma nova conexão.
    if wifi.isconnected():
        return True

    print("Conectando ao Wi-Fi...")

    # Solicita a conexão utilizando o nome e a senha
    # definidos nas configurações do projeto.
    wifi.connect(WIFI_SSID, WIFI_PASSWORD)

    # Registra o instante em que a tentativa de conexão começou.
    # ticks_ms() retorna o tempo em milissegundos do contador
    # interno do MicroPython.
    inicio = time.ticks_ms()

    # Continua verificando a conexão enquanto a ESP32
    # ainda não estiver conectada à rede.
    while not wifi.isconnected():

        # Calcula quanto tempo passou desde o início da tentativa.
        # ticks_diff() permite comparar os instantes corretamente,
        # inclusive quando o contador interno reinicia seu ciclo.
        if time.ticks_diff(time.ticks_ms(), inicio) >= 15000:

            # Se ultrapassar 15 segundos sem conexão,
            # informa a falha e retorna False.
            print("Falha ao conectar ao Wi-Fi.")
            return False

        # Permite que a ESP32 entre em estado de espera
        # enquanto aguarda a conexão, sem usar time.sleep().
        machine.idle()

    # Se a conexão for estabelecida, apresenta uma confirmação.
    print("Wi-Fi conectado!")

    # Exibe o endereço IP atribuído à ESP32 pela rede.
    print("IP:", wifi.ifconfig()[0])

    # Retorna True para indicar que a conexão foi realizada.
    return True


# ==========================================================
# LEITURA DE TODOS OS SENSORES
# ==========================================================

# Esta função reúne as leituras de todos os sensores e organiza
# os resultados em um dicionário Python.
# Posteriormente, esse dicionário será convertido para JSON
# e enviado à API hospedada no Render.
def ler_sensores():

    print("\nLendo sensores...")

    # ------------------------------------------------------
    # LEITURA DO DHT22
    # ------------------------------------------------------

    # Solicita ao DHT22 que realize uma nova medição.
    dht_sensor.measure()

    # Obtém a temperatura em graus Celsius.
    temperatura = dht_sensor.temperature()

    # Obtém a umidade relativa do ar em porcentagem.
    umidade = dht_sensor.humidity()


    # ------------------------------------------------------
    # LEITURA DO BMP280
    # ------------------------------------------------------

    # Obtém a pressão atmosférica fornecida pelo BMP280.
    # O sensor disponibiliza a pressão em Pascal (Pa).
    # A divisão por 100 converte o resultado para hectopascal
    # (hPa), unidade utilizada na dashboard e na API.
    pressao = bmp_sensor.pressure / 100


    # ------------------------------------------------------
    # LEITURA DO LDR
    # ------------------------------------------------------

    # Obtém o estado lógico da saída digital DO do módulo LDR.
    # O resultado será 0 ou 1, conforme o estado da saída.
    luminosidade = ldr_sensor.value()


    # ------------------------------------------------------
    # LEITURA DO MQ-135
    # ------------------------------------------------------

    # Chama a função que realiza as leituras do MQ-135.
    # A função retorna dois valores:
    # adc_mq135: média das leituras analógicas do sensor.
    # qualidade_ar: classificação experimental correspondente.
    adc_mq135, qualidade_ar = ler_mq135()


    # ------------------------------------------------------
    # EXIBICAO DOS RESULTADOS NO MONITOR SERIAL
    # ------------------------------------------------------

    # Apresenta as informações coletadas para facilitar
    # o acompanhamento e a identificação de possíveis erros.
    print("--------------------------------")
    print("Temperatura:", temperatura, "C")
    print("Umidade:", umidade, "%")
    print("Pressao:", round(pressao, 2), "hPa")
    print("Luminosidade (DO):", luminosidade)
    print("ADC MQ-135:", round(adc_mq135, 1))
    print("Qualidade do ar:", qualidade_ar)
    print("--------------------------------")


    # ------------------------------------------------------
    # ORGANIZACAO DOS DADOS PARA A API
    # ------------------------------------------------------

    # Cria um dicionário com as informações que serão enviadas
    # para o servidor.
    # As chaves precisam corresponder aos campos esperados
    # pela API Flask.
    #
    # O valor ADC e a classificação do MQ-135 são enviados
    # separadamente, permitindo que a API e a dashboard
    # apresentem as duas informações de forma independente.
    dados = {
        "temperatura": temperatura,
        "umidade": umidade,
        "pressao": pressao,
        "luminosidade": luminosidade,
        "adc_mq135": adc_mq135,
        "qualidade_ar": qualidade_ar
    }

    # Retorna o dicionário com as informações dos sensores
    # para que a função enviar_api() possa realizar o envio.
    return dados


# ==========================================================
# ENVIO DOS DADOS PARA A API
# ==========================================================

# Recebe o dicionário gerado pela função ler_sensores()
# e realiza o envio das informações para o servidor.
# O método POST é utilizado para transmitir dados a uma API.
def enviar_api(dados):

    # O try permite tratar possíveis erros de comunicação,
    # evitando que uma falha pontual no envio encerre o programa.
    try:

        # Realiza uma requisição HTTP POST para a API.
        resposta = urequests.post(

            # Endereço do endpoint que receberá os dados.
            API_URL,

            # Converte o dicionário Python para uma string JSON,
            # formato utilizado para transmitir as informações.
            data=ujson.dumps(dados),

            # Informa ao servidor que o conteúdo enviado
            # está no formato JSON.
            headers={
                "Content-Type": "application/json"
            }
        )

        # Exibe o código HTTP retornado pelo servidor.
        # 200 indica que a requisição foi processada com sucesso.
        # 400 indica que a requisição foi recebida, mas os dados
        # foram considerados inválidos ou incompatíveis pela API.
        print("Resposta da API:", resposta.status_code)

        # Caso o servidor retorne um código diferente de 200,
        # apresenta também a mensagem de resposta para ajudar
        # a identificar a causa da falha.
        if resposta.status_code != 200:
            print("Mensagem da API:", resposta.text)

        # Fecha a resposta HTTP após concluir a leitura.
        # Isso libera os recursos utilizados pela requisição.
        resposta.close()

    # Se ocorrer algum erro durante a comunicação,
    # a exceção será capturada e apresentada no monitor serial.
    except Exception as erro:

        print("Erro ao enviar dados:", erro)


# ==========================================================
# PROGRAMA PRINCIPAL
# ==========================================================

# Apresenta o nome do projeto no monitor serial
# para identificar o início da execução.
print("================================")
print(" ESTACAO METEOROLOGICA ESP32")
print("================================")


# ----------------------------------------------------------
# PRIMEIRA CONEXAO COM A INTERNET
# ----------------------------------------------------------

# Antes de começar a enviar os dados, o programa tenta
# estabelecer uma conexão com a rede Wi-Fi.
# A função conectar_wifi() retorna True se conseguir conectar
# ou False caso ocorra uma falha.
conectar_wifi()


# Registra o instante inicial do controle de intervalo.
# Esse valor será utilizado para determinar quando deverá
# ocorrer o próximo ciclo de leitura e envio dos sensores.
ultimo_envio = time.ticks_ms()


# ----------------------------------------------------------
# LOOP PRINCIPAL
# ----------------------------------------------------------

# O while True mantém o programa funcionando continuamente.
# Enquanto a ESP32 estiver ligada, o programa verifica
# se chegou o momento de realizar uma nova leitura e envio.
while True:

    # Obtém o instante atual em milissegundos.
    agora = time.ticks_ms()

    # Verifica quanto tempo passou desde o último ciclo.
    # Quando a diferença atingir INTERVALO_ENVIO, o programa
    # poderá iniciar uma nova leitura e enviar os dados.
    if time.ticks_diff(agora, ultimo_envio) >= INTERVALO_ENVIO:

        # Atualiza o instante de referência para controlar
        # o intervalo do próximo ciclo.
        ultimo_envio = agora


        # --------------------------------------------------
        # VERIFICACAO DA CONEXAO WI-FI
        # --------------------------------------------------

        # Antes de realizar o envio, verifica se a ESP32
        # continua conectada à rede.
        if not wifi.isconnected():

            print("Wi-Fi desconectado.")

            # Caso a conexão tenha sido perdida, tenta conectar
            # novamente à rede configurada.
            conectar_wifi()


        # --------------------------------------------------
        # LEITURA E ENVIO DOS DADOS
        # --------------------------------------------------

        # Só realiza as leituras e o envio se a ESP32
        # estiver conectada à rede Wi-Fi.
        if wifi.isconnected():

            # Trata possíveis erros durante a leitura dos sensores
            # ou durante o processamento dos dados.
            try:

                # Executa a leitura de todos os sensores e recebe
                # o dicionário com os resultados.
                dados = ler_sensores()

                # Envia o dicionário para a API hospedada no Render.
                enviar_api(dados)

            except Exception as erro:

                # Apresenta o erro no monitor serial sem encerrar
                # o loop principal.
                print("Erro na leitura dos sensores:", erro)


    # Permite que a ESP32 entre em estado de espera enquanto
    # não houver uma tarefa imediata a executar.
    # Isso evita manter o processador executando verificações
    # continuamente sem necessidade e não utiliza sleep().
    machine.idle()

