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
import time


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
# PARAMETROS DO FILTRO DE VARIACAO TEMPORAL
# ==========================================================

# Valores iniciais conservadores. Eles podem ser ajustados após
# observar o comportamento real dos sensores durante os testes.
#
# Temperatura: admite variação de até 1,0 °C por segundo.
# O intervalo mínimo de 2 segundos considera o intervalo de
# atualização do DHT22 no firmware atual.
TAXA_MAXIMA_TEMPERATURA = 1.0  # °C por segundo
INTERVALO_MINIMO_TEMPERATURA = 2.0  # segundos

# Pressão: admite variação de até 0,5 hPa por segundo.
TAXA_MAXIMA_PRESSAO = 0.5  # hPa por segundo
INTERVALO_MINIMO_PRESSAO = 1.0  # segundos


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

# Guarda o instante monotônico da última temperatura e pressão
# aceitas. Esses valores permitem calcular o tempo entre leituras.
ultima_temperatura_aceita = None
ultima_pressao_aceita = None

# Guarda os avisos gerados na requisição mais recente.
avisos_validacao = []


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
# FILTRO TEMPORAL: TEMPERATURA E PRESSAO
# ==========================================================

def filtrar_variacoes_temporais(novos_dados_validos, instante_atual):

    global ultima_temperatura_aceita, ultima_pressao_aceita

    # Cria uma cópia para preservar os dados recebidos.
    # Somente temperatura e pressão podem ser substituídas
    # pelos últimos valores aceitos caso uma variação seja suspeita.
    dados_filtrados = novos_dados_validos.copy()
    avisos = []

    # ------------------------------------------------------
    # 1. FILTRO DA TEMPERATURA
    # ------------------------------------------------------

    temperatura_anterior = dados["temperatura"]

    # A primeira leitura válida serve como referência inicial.
    if temperatura_anterior is None or ultima_temperatura_aceita is None:

        ultima_temperatura_aceita = instante_atual

    else:

        tempo_decorrido = max(
            instante_atual - ultima_temperatura_aceita,
            INTERVALO_MINIMO_TEMPERATURA
        )

        variacao = abs(
            novos_dados_validos["temperatura"] - temperatura_anterior
        )

        variacao_permitida = (
            TAXA_MAXIMA_TEMPERATURA * tempo_decorrido
        )

        if variacao > variacao_permitida:

            # Mantém a última temperatura aceita.
            # O restante dos sensores continua sendo atualizado.
            dados_filtrados["temperatura"] = temperatura_anterior

            avisos.append(
                "Temperatura preservada: variação de "
                f"{variacao:.2f} °C em aproximadamente "
                f"{tempo_decorrido:.1f} s; limite calculado de "
                f"{variacao_permitida:.2f} °C."
            )

            # Não atualiza o instante da última leitura aceita.
            # Assim, uma mudança persistente poderá ser aceita
            # quando se tornar plausível em relação ao tempo decorrido.

        else:

            ultima_temperatura_aceita = instante_atual


    # ------------------------------------------------------
    # 2. FILTRO DA PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    pressao_anterior = dados["pressao"]

    # A primeira leitura válida serve como referência inicial.
    if pressao_anterior is None or ultima_pressao_aceita is None:

        ultima_pressao_aceita = instante_atual

    else:

        tempo_decorrido = max(
            instante_atual - ultima_pressao_aceita,
            INTERVALO_MINIMO_PRESSAO
        )

        variacao = abs(
            novos_dados_validos["pressao"] - pressao_anterior
        )

        variacao_permitida = TAXA_MAXIMA_PRESSAO * tempo_decorrido

        if variacao > variacao_permitida:

            # Mantém a última pressão aceita.
            # O restante dos sensores continua sendo atualizado.
            dados_filtrados["pressao"] = pressao_anterior

            avisos.append(
                "Pressão preservada: variação de "
                f"{variacao:.2f} hPa em aproximadamente "
                f"{tempo_decorrido:.1f} s; limite calculado de "
                f"{variacao_permitida:.2f} hPa."
            )

            # Não atualiza o instante da última leitura aceita.
            # Uma mudança persistente poderá ser aceita após tempo suficiente.

        else:

            ultima_pressao_aceita = instante_atual


    return dados_filtrados, avisos


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

    global dados, ultima_atualizacao, avisos_validacao


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
        # EXECUCAO DAS VALIDACOES FISICAS E DE FORMATO
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
        # SELECAO DOS CAMPOS ESPERADOS PELA API
        # --------------------------------------------------

        # Campos extras enviados no JSON são ignorados.
        novos_dados_validos = {
            campo: novos_dados[campo]
            for campo in CAMPOS_OBRIGATORIOS
        }


        # --------------------------------------------------
        # APLICACAO DO FILTRO TEMPORAL
        # --------------------------------------------------

        # Usa relógio monotônico para calcular intervalos.
        # Ele é mais adequado que o horário civil para medir duração.
        instante_atual = time.monotonic()

        dados_filtrados, avisos_validacao = filtrar_variacoes_temporais(
            novos_dados_validos,
            instante_atual
        )


        # --------------------------------------------------
        # ATUALIZACAO DOS DADOS
        # --------------------------------------------------

        # Se temperatura ou pressão forem suspeitas, seus últimos
        # valores aceitos são mantidos. Os outros sensores são atualizados.
        dados = dados_filtrados


        # --------------------------------------------------
        # REGISTRO DO HORARIO DA NOVA MEDICAO
        # --------------------------------------------------

        # Atualiza o horário porque o pacote foi recebido e os demais
        # campos passaram pelas validações, mesmo que um dos sensores
        # tenha tido seu valor anterior preservado pelo filtro temporal.
        #
        # O formato ISO 8601 permite que o JavaScript converta o horário
        # corretamente para Date.
        ultima_atualizacao = datetime.now(timezone.utc).isoformat()


        # --------------------------------------------------
        # RESPOSTA DO POST
        # --------------------------------------------------

        return jsonify({
            "mensagem": "Dados recebidos e processados com sucesso.",
            "dados": dados,
            "avisos_validacao": avisos_validacao,
            "ultima_atualizacao": ultima_atualizacao
        }), 200


    # ======================================================
    # CONSULTA DOS DADOS (GET)
    # ======================================================

    # O GET não altera os dados nem o horário.
    # Apenas retorna a última medição armazenada e os avisos
    # referentes à requisição mais recente.
    return jsonify({
        **dados,
        "ultima_atualizacao": ultima_atualizacao,
        "avisos_validacao": avisos_validacao
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
