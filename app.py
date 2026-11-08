
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

from datetime import datetime, timezone


# ==========================================================
# INICIALIZACAO DA APLICACAO
# ==========================================================

# Cria a aplicação Flask, responsável pelas rotas da API.
app = Flask(__name__)


# ==========================================================
# CAMPOS OBRIGATORIOS DA API
# ==========================================================

# Define os seis campos que a ESP32 deve enviar.
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

# Armazena as últimas medições válidas recebidas da ESP32.
dados = {
    "temperatura": None,
    "umidade": None,
    "pressao": None,
    "luminosidade": None,
    "adc_mq135": None,
    "qualidade_ar": None
}

# Armazena o horário da última medição válida recebida.
# Inicialmente não existe nenhuma medição.
ultima_atualizacao = None


# ==========================================================
# FUNCAO AUXILIAR: VERIFICACAO DE NUMEROS
# ==========================================================

def numero_valido(valor):

    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


# ==========================================================
# FUNCAO AUXILIAR: CLASSIFICACAO DA QUALIDADE DO AR
# ==========================================================

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

def validar_dados(novos_dados):

    erros = []

    # ------------------------------------------------------
    # 1. VERIFICACAO DOS CAMPOS OBRIGATORIOS
    # ------------------------------------------------------

    campos_faltantes = [
        campo
        for campo in CAMPOS_OBRIGATORIOS
        if campo not in novos_dados
    ]

    for campo in campos_faltantes:
        erros.append(
            f"O campo '{campo}' não foi enviado."
        )


    # ------------------------------------------------------
    # 2. VALIDACAO DA TEMPERATURA
    # ------------------------------------------------------

    temperatura = novos_dados.get("temperatura")

    if not numero_valido(temperatura):

        erros.append(
            "Temperatura inválida. Envie um número."
        )

    elif not -40 <= temperatura <= 80:

        erros.append(
            "Temperatura fora da faixa permitida: "
            "utilize valores entre -40 e 80 °C."
        )


    # ------------------------------------------------------
    # 3. VALIDACAO DA UMIDADE
    # ------------------------------------------------------

    umidade = novos_dados.get("umidade")

    if not numero_valido(umidade):

        erros.append(
            "Umidade inválida. Envie um número."
        )

    elif not 0 <= umidade <= 100:

        erros.append(
            "Umidade fora da faixa permitida: "
            "utilize valores entre 0 e 100%."
        )


    # ------------------------------------------------------
    # 4. VALIDACAO DA PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    pressao = novos_dados.get("pressao")

    if not numero_valido(pressao):

        erros.append(
            "Pressão inválida. Envie um número."
        )

    elif not 300 <= pressao <= 1100:

        erros.append(
            "Pressão fora da faixa permitida: "
            "utilize valores entre 300 e 1100 hPa."
        )


    # ------------------------------------------------------
    # 5. VALIDACAO DA LUMINOSIDADE
    # ------------------------------------------------------

    luminosidade = novos_dados.get("luminosidade")

    # O LDR utiliza a saída digital DO.
    # Por isso, somente os estados inteiros 0 e 1 são aceitos.
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

    adc = novos_dados.get("adc_mq135")

    if not numero_valido(adc):

        erros.append(
            "ADC do MQ-135 inválido. Envie um número."
        )

    elif not 0 <= adc <= 4095:

        erros.append(
            "ADC do MQ-135 fora da faixa permitida: "
            "utilize valores entre 0 e 4095."
        )


    # ------------------------------------------------------
    # 7. VALIDACAO DA CLASSIFICACAO DA QUALIDADE DO AR
    # ------------------------------------------------------

    qualidade = novos_dados.get("qualidade_ar")

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

    if numero_valido(adc) and isinstance(qualidade, str):

        classificacao_esperada = classificar_qualidade_ar(adc)

        if qualidade != classificacao_esperada:

            erros.append(
                "Classificação da qualidade do ar incompatível "
                f"com o ADC. Para o valor {adc}, "
                f"o resultado esperado é {classificacao_esperada}."
            )


    return erros


# ==========================================================
# ROTA DA DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    return render_template("index.html")


# ==========================================================
# ROTA INICIAL DA API
# ==========================================================

@app.route("/")
def inicio():

    return jsonify({
        "mensagem": "API FUNCIONANDO."
    })


# ==========================================================
# ROTA DE RECEBIMENTO E CONSULTA DOS DADOS
# ==========================================================

# GET: consulta as últimas medições armazenadas.
# POST: recebe novas medições enviadas pela ESP32.
@app.route("/dados", methods=["GET", "POST"])
def gerenciar_dados():

    global dados, ultima_atualizacao


    # ======================================================
    # RECEBIMENTO DE DADOS (POST)
    # ======================================================

    if request.method == "POST":

        # Tenta interpretar o conteúdo recebido como JSON.
        novos_dados = request.get_json(silent=True)


        # --------------------------------------------------
        # VERIFICACAO DO FORMATO JSON
        # --------------------------------------------------

        if not isinstance(novos_dados, dict):

            return jsonify({
                "erro": "Envie um objeto JSON válido."
            }), 400


        # --------------------------------------------------
        # EXECUCAO DAS VALIDACOES
        # --------------------------------------------------

        erros = validar_dados(novos_dados)

        # Se houver erros, rejeita a requisição.
        # Os dados anteriores permanecem armazenados.
        if erros:

            return jsonify({

                "erro": "Dados inválidos.",

                "detalhes": erros

            }), 400


        # --------------------------------------------------
        # ATUALIZACAO DOS DADOS
        # --------------------------------------------------

        # Armazena somente os campos esperados pela API.
        # Campos extras enviados no JSON são ignorados.
        novos_dados_validos = {

            campo: novos_dados[campo]

            for campo in CAMPOS_OBRIGATORIOS
        }

        dados = novos_dados_validos


        # --------------------------------------------------
        # REGISTRO DO HORARIO DA NOVA MEDICAO
        # --------------------------------------------------

        # Atualiza o horário somente depois que a medição
        # passou por todas as validações e foi armazenada.
        #
        # O formato ISO 8601 permite que o JavaScript
        # converta o horário corretamente para Date.
        ultima_atualizacao = datetime.now(timezone.utc).isoformat()


        # --------------------------------------------------
        # RESPOSTA DO POST
        # --------------------------------------------------

        return jsonify({

            "mensagem": "Dados recebidos e validados com sucesso.",

            "dados": dados,

            "ultima_atualizacao": ultima_atualizacao

        }), 200


    # ======================================================
    # CONSULTA DOS DADOS (GET)
    # ======================================================

    # O GET não altera os dados nem o horário.
    # Apenas retorna a última medição válida armazenada.
    return jsonify({

        **dados,

        "ultima_atualizacao": ultima_atualizacao

    })


# ==========================================================
# EXECUCAO LOCAL DA APLICACAO
# ==========================================================

if __name__ == "__main__":

    # host="0.0.0.0": aceita conexões externas.
    # port=5000: utiliza a porta 5000.
    # debug=False: mantém o modo de depuração desativado.
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
