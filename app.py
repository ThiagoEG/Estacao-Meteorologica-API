
# ==========================================================
# IMPORTACAO DAS BIBLIOTECAS
# ==========================================================

# Flask: framework utilizado para desenvolver a API.
# jsonify: transforma dados Python em respostas JSON.
# request: permite acessar as informações recebidas nas requisições.
# render_template: apresenta os arquivos HTML da dashboard.
from flask import Flask, jsonify, request, render_template

# math: disponibiliza funções matemáticas.
# Utilizaremos isfinite() para rejeitar valores infinitos e NaN.
import math


# ==========================================================
# INICIALIZACAO DA APLICACAO
# ==========================================================

# Cria a aplicação Flask, responsável pelas rotas da API.
app = Flask(__name__)


# ==========================================================
# CAMPOS OBRIGATORIOS DA API
# ==========================================================

# Define os seis campos que a ESP32 deve enviar.
#
# Essa estrutura também será utilizada para organizar
# os dados recebidos e evitar armazenar campos desconhecidos.
CAMPOS_OBRIGATORIOS = (
    "temperatura",
    "umidade",
    "pressao",
    "luminosidade",
    "adc_mq135",
    "qualidade_ar"
)


# ==========================================================
# CLASSIFICACOES PERMITIDAS PARA O MQ-135
# ==========================================================

# Lista das classificações aceitas pela API.
#
# Os nomes devem corresponder exatamente às classificações
# utilizadas na ESP32.
CLASSIFICACOES_AR = (
    "EXCELENTE",
    "BOA",
    "MODERADA",
    "RUIM",
    "PESSIMA"
)


# ==========================================================
# ARMAZENAMENTO DOS DADOS DOS SENSORES
# ==========================================================

# Dicionário que armazena as últimas medições válidas
# recebidas da ESP32.
#
# Inicialmente, os campos recebem None porque ainda não
# existem medições disponíveis.
#
# Os dados permanecem na memória da aplicação.
dados = {
    "temperatura": None,
    "umidade": None,
    "pressao": None,
    "luminosidade": None,
    "adc_mq135": None,
    "qualidade_ar": None
}


# ==========================================================
# FUNCAO AUXILIAR: VERIFICACAO DE NUMEROS
# ==========================================================

# Verifica se determinado valor é um número válido.
#
# São aceitos números inteiros e decimais.
# Valores booleanos, textos, NaN e infinito são rejeitados.
#
# Em Python, bool é uma subclasse de int.
# Por isso, precisamos rejeitá-lo separadamente.

def numero_valido(valor):

    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


# ==========================================================
# FUNCAO AUXILIAR: CLASSIFICACAO DA QUALIDADE DO AR
# ==========================================================

# Reproduz as mesmas faixas utilizadas pela ESP32.
#
# Essa função permite que a API confira se a classificação
# recebida corresponde ao valor ADC informado.

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
# FUNCAO PRINCIPAL DE VALIDACAO
# ==========================================================

# Recebe o objeto JSON enviado pela ESP32 e verifica
# se todas as informações estão presentes e são plausíveis.
#
# A função retorna uma lista com os erros encontrados.
#
# Se a lista estiver vazia, significa que os dados passaram
# por todas as verificações.

def validar_dados(novos_dados):

    erros = []


    # ------------------------------------------------------
    # 1. VERIFICACAO DOS CAMPOS OBRIGATORIOS
    # ------------------------------------------------------

    # Identifica quais campos obrigatórios não foram enviados.
    campos_faltantes = [
        campo
        for campo in CAMPOS_OBRIGATORIOS
        if campo not in novos_dados
    ]

    # Adiciona uma mensagem de erro para cada campo ausente.
    for campo in campos_faltantes:
        erros.append(
            f"O campo '{campo}' não foi enviado."
        )


    # ------------------------------------------------------
    # 2. VALIDACAO DA TEMPERATURA
    # ------------------------------------------------------

    # Obtém o valor da temperatura recebido no JSON.
    temperatura = novos_dados.get("temperatura")

    # Primeiro verifica se o valor é numérico e válido.
    if not numero_valido(temperatura):

        erros.append(
            "Temperatura inválida. Envie um número."
        )

    # Depois verifica se está dentro da faixa de medição
    # especificada para o DHT22.
    elif not -40 <= temperatura <= 80:

        erros.append(
            "Temperatura fora da faixa permitida: "
            "utilize valores entre -40 e 80 °C."
        )


    # ------------------------------------------------------
    # 3. VALIDACAO DA UMIDADE
    # ------------------------------------------------------

    # Obtém a umidade relativa do ar.
    umidade = novos_dados.get("umidade")

    # Verifica se o valor é numérico.
    if not numero_valido(umidade):

        erros.append(
            "Umidade inválida. Envie um número."
        )

    # A umidade relativa deve estar entre 0 e 100%.
    elif not 0 <= umidade <= 100:

        erros.append(
            "Umidade fora da faixa permitida: "
            "utilize valores entre 0 e 100%."
        )


    # ------------------------------------------------------
    # 4. VALIDACAO DA PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    # Obtém a pressão atmosférica recebida em hPa.
    pressao = novos_dados.get("pressao")

    # Verifica se o valor é numérico.
    if not numero_valido(pressao):

        erros.append(
            "Pressão inválida. Envie um número."
        )

    # Confere a faixa de medição do BMP280.
    elif not 300 <= pressao <= 1100:

        erros.append(
            "Pressão fora da faixa permitida: "
            "utilize valores entre 300 e 1100 hPa."
        )


    # ------------------------------------------------------
    # 5. VALIDACAO DA LUMINOSIDADE
    # ------------------------------------------------------

    # Obtém a leitura digital do módulo LDR.
    luminosidade = novos_dados.get("luminosidade")

    # O módulo está utilizando sua saída digital (DO).
    # Por isso, somente os estados 0 e 1 são aceitos.
    #
    # Também rejeitamos valores booleanos, apesar de
    # True e False serem tratados como números em Python.
    if (
        not isinstance(luminosidade, int)
        or isinstance(luminosidade, bool)
        or luminosidade not in (0, 1)
    ):

        erros.append(
            "Luminosidade inválida. "
            "A saída digital deve ser 0 ou 1."
        )


    # ------------------------------------------------------
    # 6. VALIDACAO DO ADC DO MQ-135
    # ------------------------------------------------------

    # Obtém a média das leituras analógicas do MQ-135.
    adc = novos_dados.get("adc_mq135")

    # Verifica se o valor recebido é numérico.
    if not numero_valido(adc):

        erros.append(
            "ADC do MQ-135 inválido. Envie um número."
        )

    # O conversor utilizado pela ESP32 trabalha com
    # leituras de 0 a 4095.
    elif not 0 <= adc <= 4095:

        erros.append(
            "ADC do MQ-135 fora da faixa permitida: "
            "utilize valores entre 0 e 4095."
        )


    # ------------------------------------------------------
    # 7. VALIDACAO DA CLASSIFICACAO DA QUALIDADE DO AR
    # ------------------------------------------------------

    # Obtém a classificação enviada pela ESP32.
    qualidade = novos_dados.get("qualidade_ar")

    # Verifica se a classificação é um texto permitido.
    if (
        not isinstance(qualidade, str)
        or qualidade not in CLASSIFICACOES_AR
    ):

        erros.append(
            "Qualidade do ar inválida. "
            "Utilize EXCELENTE, BOA, MODERADA, RUIM ou PESSIMA."
        )


    # ------------------------------------------------------
    # 8. VERIFICACAO DA COERENCIA ENTRE ADC E CLASSIFICACAO
    # ------------------------------------------------------

    # Além de verificar se cada campo é válido separadamente,
    # conferimos se a classificação corresponde ao ADC.
    #
    # Essa comparação só é realizada quando os dois valores
    # passaram pelas verificações anteriores.

    if numero_valido(adc) and isinstance(qualidade, str):

        # Calcula a classificação esperada com base no ADC.
        classificacao_esperada = classificar_qualidade_ar(adc)

        # Compara o resultado calculado com o texto recebido.
        if qualidade != classificacao_esperada:

            erros.append(
                "Classificação da qualidade do ar incompatível "
                f"com o ADC. Para o valor {adc}, "
                f"o resultado esperado é {classificacao_esperada}."
            )


    # Retorna todas as mensagens de erro encontradas.
    return erros


# ==========================================================
# ROTA DA DASHBOARD
# ==========================================================

# Disponibiliza a página HTML da dashboard.
@app.route("/dashboard")
def dashboard():

    # Procura o arquivo index.html dentro da pasta templates.
    return render_template("index.html")


# ==========================================================
# ROTA INICIAL DA API
# ==========================================================

# Disponibiliza uma mensagem simples para verificar
# se a API está funcionando.
@app.route("/")
def inicio():

    return jsonify({
        "mensagem": "API FUNCIONANDO."
    })


# ==========================================================
# ROTA DE RECEBIMENTO E CONSULTA DOS DADOS
# ==========================================================

# GET: permite consultar as últimas medições armazenadas.
#
# POST: recebe novas medições enviadas pela ESP32.
@app.route("/dados", methods=["GET", "POST"])
def gerenciar_dados():

    # Permite atualizar o dicionário global de dados.
    global dados


    # ======================================================
    # RECEBIMENTO DE DADOS (POST)
    # ======================================================

    if request.method == "POST":

        # Tenta interpretar o conteúdo recebido como JSON.
        #
        # Se o conteúdo não for um JSON válido,
        # o resultado será None.
        novos_dados = request.get_json(silent=True)


        # --------------------------------------------------
        # VERIFICACAO DO FORMATO JSON
        # --------------------------------------------------

        # A API espera receber um objeto JSON, que será
        # representado como um dicionário em Python.
        if not isinstance(novos_dados, dict):

            return jsonify({
                "erro": "Envie um objeto JSON válido."
            }), 400


        # --------------------------------------------------
        # EXECUCAO DAS VALIDACOES
        # --------------------------------------------------

        # Envia os dados recebidos para a função de validação.
        # Ela retorna uma lista com todos os problemas encontrados.
        erros = validar_dados(novos_dados)


        # Caso exista pelo menos um erro, a requisição
        # será rejeitada e os dados armazenados não serão alterados.
        if erros:

            return jsonify({

                "erro": "Dados inválidos.",

                "detalhes": erros

            }), 400


        # --------------------------------------------------
        # ATUALIZACAO DOS DADOS
        # --------------------------------------------------

        # Se todas as validações forem aprovadas,
        # cria um novo dicionário somente com os campos
        # esperados pela API.
        #
        # Campos extras enviados no JSON são ignorados.
        novos_dados_validos = {

            campo: novos_dados[campo]

            for campo in CAMPOS_OBRIGATORIOS
        }

        # Substitui os dados anteriores pelas novas medições.
        #
        # Essa atualização só acontece depois que todos
        # os campos passam pelas validações.
        dados = novos_dados_validos


        # Retorna uma confirmação de recebimento
        # acompanhada dos dados armazenados.
        return jsonify({

            "mensagem": "Dados recebidos e validados com sucesso.",

            "dados": dados

        }), 200


    # ======================================================
    # CONSULTA DOS DADOS (GET)
    # ======================================================

    # Quando a dashboard ou outro cliente realiza uma
    # requisição GET, a API retorna as últimas medições válidas.
    return jsonify(dados)


# ==========================================================
# EXECUCAO LOCAL DA APLICACAO
# ==========================================================

# Verifica se o arquivo está sendo executado diretamente.
#
# Essa condição permite iniciar o servidor Flask localmente
# sem executar essa parte quando o módulo for importado.
if __name__ == "__main__":

    # Inicia o servidor Flask.
    #
    # host="0.0.0.0": aceita conexões externas.
    # port=5000: utiliza a porta 5000.
    # debug=False: mantém o modo de depuração desativado.
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
