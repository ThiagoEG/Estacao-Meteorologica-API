# ==========================================================
# IMPORTACAO DAS BIBLIOTECAS
# ==========================================================

# Flask cria a aplicação, jsonify gera respostas JSON, request
# lê o corpo das requisições e render_template carrega o HTML.
from flask import Flask, jsonify, request, render_template

# datetime e timezone registram o horário das medições em UTC.
from datetime import datetime, timezone

# math permite verificar se os números recebidos são finitos.
import math

# time.monotonic mede intervalos sem depender do relógio do sistema.
import time


# ==========================================================
# INICIALIZACAO DA APLICACAO
# ==========================================================

# Cria a aplicação Flask que receberá e processará as requisições.
app = Flask(__name__)


# ==========================================================
# CAMPOS E CLASSIFICACOES DA API
# ==========================================================

# Define os campos obrigatórios enviados pela ESP32.
# O ADC é mantido como leitura bruta para diagnóstico.
CAMPOS_OBRIGATORIOS = (
    "temperatura",
    "umidade",
    "pressao",
    "luminosidade",
    "adc_mq135",
    "ppm",
    "indicador_ppm_estimado",
)

# Lista as classificações aceitas pela API.
CLASSIFICACOES_PPM = (
    "EXCELENTE",
    "BOA",
    "MODERADA",
    "RUIM",
    "PESSIMA",
    "LEITURA_INVALIDA",
)

# Define os limites de classificação em PPM.
# Os valores correspondem às conversões aproximadas dos limites ADC definidos.
LIMITE_PPM_EXCELENTE = 234.2
LIMITE_PPM_BOA = 609.1
LIMITE_PPM_MODERADA = 1953.0
LIMITE_PPM_RUIM = 7041.6


# ==========================================================
# PARAMETROS DO FILTRO TEMPORAL
# ==========================================================

# Define a variação máxima de temperatura permitida por segundo.
TAXA_MAXIMA_TEMPERATURA = 1.0

# Define o intervalo mínimo utilizado no cálculo da variação da temperatura.
INTERVALO_MINIMO_TEMPERATURA = 2.0

# Define a variação máxima de pressão permitida por segundo.
TAXA_MAXIMA_PRESSAO = 0.5

# Define o intervalo mínimo utilizado no cálculo da variação da pressão.
INTERVALO_MINIMO_PRESSAO = 1.0


# ==========================================================
# ARMAZENAMENTO DOS DADOS DOS SENSORES
# ==========================================================

# Armazena a última medição válida de cada sensor.
# None indica que ainda não existe uma leitura recebida.
dados = {
    "temperatura": None,
    "umidade": None,
    "pressao": None,
    "luminosidade": None,
    "adc_mq135": None,
    "ppm": None,
    "indicador_ppm_estimado": None,
}

# Armazena o horário da última atualização recebida.
ultima_atualizacao = None

# Guarda o instante da última temperatura e pressão aceitas.
# Esses valores são utilizados pelo filtro temporal.
ultima_temperatura_aceita = None
ultima_pressao_aceita = None

# Armazena os avisos gerados pela validação mais recente.
avisos_validacao = []


# ==========================================================
# FUNCOES AUXILIARES
# ==========================================================

def numero_valido(valor):
    # Verifica se o valor é numérico, finito e não booleano.
    # bool é excluído porque, em Python, também é considerado um tipo inteiro.
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


def classificar_indicador_ppm(valor):
    # Compara a concentração estimada com os limites definidos.
    if valor <= LIMITE_PPM_EXCELENTE:
        return "EXCELENTE"

    elif valor <= LIMITE_PPM_BOA:
        return "BOA"

    elif valor <= LIMITE_PPM_MODERADA:
        return "MODERADA"

    elif valor <= LIMITE_PPM_RUIM:
        return "RUIM"

    else:
        return "PESSIMA"


# ==========================================================
# VALIDACAO DOS DADOS RECEBIDOS
# ==========================================================

def validar_dados(novos_dados):

    # Armazena as mensagens referentes aos campos inválidos.
    erros = []

    # Identifica os campos obrigatórios que não foram enviados.
    campos_faltantes = [
        campo
        for campo in CAMPOS_OBRIGATORIOS
        if campo not in novos_dados
    ]

    # Adiciona uma mensagem para cada campo ausente.
    for campo in campos_faltantes:
        erros.append(
            f"O campo '{campo}' não foi enviado."
        )

    # ------------------------------------------------------
    # 1. VALIDACAO DA TEMPERATURA
    # ------------------------------------------------------

    # Obtém a temperatura enviada pelo DHT22.
    temperatura = novos_dados.get("temperatura")

    # Verifica se a temperatura é um número finito.
    if not numero_valido(temperatura):
        erros.append("Temperatura inválida. Envie um número finito.")

    # Verifica se a temperatura está dentro da faixa permitida.
    elif not -40 <= temperatura <= 80:
        erros.append(
            "Temperatura fora da faixa permitida: "
            "utilize valores entre -40 e 80 °C."
        )

    # ------------------------------------------------------
    # 2. VALIDACAO DA UMIDADE
    # ------------------------------------------------------

    # Obtém a umidade relativa enviada pelo DHT22.
    umidade = novos_dados.get("umidade")

    # Verifica se a umidade é um número finito.
    if not numero_valido(umidade):
        erros.append("Umidade inválida. Envie um número finito.")

    # A umidade relativa deve permanecer entre 0 e 100%.
    elif not 0 <= umidade <= 100:
        erros.append(
            "Umidade fora da faixa permitida: "
            "utilize valores entre 0 e 100%."
        )

    # ------------------------------------------------------
    # 3. VALIDACAO DA PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    # Obtém a pressão enviada pelo BMP280.
    pressao = novos_dados.get("pressao")

    # Verifica se a pressão é um número finito.
    if not numero_valido(pressao):
        erros.append("Pressão inválida. Envie um número finito.")

    # Verifica se a pressão está dentro da faixa permitida.
    elif not 300 <= pressao <= 1100:
        erros.append(
            "Pressão fora da faixa permitida: "
            "utilize valores entre 300 e 1100 hPa."
        )

    # ------------------------------------------------------
    # 4. VALIDACAO DA LUMINOSIDADE
    # ------------------------------------------------------

    # Obtém o estado digital enviado pelo módulo LDR.
    luminosidade = novos_dados.get("luminosidade")

    # Aceita somente os inteiros 0 e 1.
    # A verificação de bool impede que True e False sejam aceitos como inteiros.
    if (
        not isinstance(luminosidade, int)
        or isinstance(luminosidade, bool)
        or luminosidade not in (0, 1)
    ):
        erros.append(
            "Luminosidade inválida. A saída digital deve ser 0 ou 1."
        )

    # ------------------------------------------------------
    # 5. VALIDACAO DO ADC DO MQ-135
    # ------------------------------------------------------

    # Obtém a média das leituras analógicas do MQ-135.
    adc = novos_dados.get("adc_mq135")

    # Verifica se o ADC é um número finito.
    if not numero_valido(adc):
        erros.append("ADC do MQ-135 inválido. Envie um número finito.")

    # O ADC de 12 bits da ESP32 utiliza valores entre 0 e 4095.
    elif not 0 <= adc <= 4095:
        erros.append(
            "ADC do MQ-135 fora da faixa permitida: "
            "utilize valores entre 0 e 4095."
        )

    # ------------------------------------------------------
    # 6. VALIDACAO DO PPM E DO INDICADOR
    # ------------------------------------------------------

    # Obtém a estimativa de PPM e sua respectiva classificação.
    ppm = novos_dados.get("ppm")
    indicador_ppm = novos_dados.get("indicador_ppm_estimado")

    # Quando a leitura não pode ser calculada, o firmware deve enviar
    # ppm como null e utilizar a classificação LEITURA_INVALIDA.
    if ppm is None:

        if indicador_ppm != "LEITURA_INVALIDA":
            erros.append(
                "Quando 'ppm' for nulo, "
                "'indicador_ppm_estimado' deve ser LEITURA_INVALIDA."
            )

    # Verifica se o PPM é um número finito.
    elif not numero_valido(ppm):
        erros.append(
            "PPM inválido. Envie um número finito ou null."
        )

    # Impede valores negativos ou excessivamente elevados.
    elif not 0 <= ppm <= 1_000_000:
        erros.append(
            "PPM fora da faixa permitida: "
            "utilize valores entre 0 e 1.000.000."
        )

    # Verifica se a classificação pertence às opções permitidas.
    if (
        not isinstance(indicador_ppm, str)
        or indicador_ppm not in CLASSIFICACOES_PPM
    ):
        erros.append(
            "Indicador PPM inválido. Utilize EXCELENTE, BOA, MODERADA, "
            "RUIM, PESSIMA ou LEITURA_INVALIDA."
        )

    # Confere se a classificação corresponde à faixa calculada pela API.
    elif numero_valido(ppm):

        indicador_esperado = classificar_indicador_ppm(ppm)

        if indicador_ppm != indicador_esperado:
            erros.append(
                "Indicador PPM incompatível com o valor enviado. "
                f"Para {ppm} ppm, o resultado esperado é {indicador_esperado}."
            )

    # Retorna todos os erros encontrados.
    return erros


# ==========================================================
# FILTRO DE VARIACOES TEMPORAIS
# ==========================================================

def filtrar_variacoes_temporais(novos_dados_validos, instante_atual):

    # Permite atualizar os instantes das últimas leituras aceitas.
    global ultima_temperatura_aceita, ultima_pressao_aceita

    # Cria uma cópia para preservar o pacote original recebido.
    dados_filtrados = novos_dados_validos.copy()

    # Armazena avisos gerados durante a análise das medições.
    avisos = []

    # ------------------------------------------------------
    # 1. FILTRO DA TEMPERATURA
    # ------------------------------------------------------

    # Recupera a última temperatura armazenada.
    temperatura_anterior = dados["temperatura"]

    # A primeira leitura válida é utilizada como referência.
    if temperatura_anterior is None or ultima_temperatura_aceita is None:

        ultima_temperatura_aceita = instante_atual

    else:

        # Calcula o tempo desde a última temperatura aceita.
        # O intervalo mínimo evita divisões por períodos muito curtos.
        tempo_decorrido = max(
            instante_atual - ultima_temperatura_aceita,
            INTERVALO_MINIMO_TEMPERATURA
        )

        # Calcula a diferença absoluta entre as temperaturas.
        variacao = abs(
            novos_dados_validos["temperatura"] - temperatura_anterior
        )

        # Calcula a variação máxima permitida para o intervalo.
        variacao_permitida = (
            TAXA_MAXIMA_TEMPERATURA * tempo_decorrido
        )

        if variacao > variacao_permitida:

            # Preserva a última temperatura aceita.
            dados_filtrados["temperatura"] = temperatura_anterior

            # Registra a diferença encontrada para diagnóstico.
            avisos.append(
                "Temperatura preservada: variação de "
                f"{variacao:.2f} °C em aproximadamente "
                f"{tempo_decorrido:.1f} s; limite calculado de "
                f"{variacao_permitida:.2f} °C."
            )

        else:

            # Atualiza o instante quando a nova temperatura é aceita.
            ultima_temperatura_aceita = instante_atual

    # ------------------------------------------------------
    # 2. FILTRO DA PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    # Recupera a última pressão armazenada.
    pressao_anterior = dados["pressao"]

    # A primeira leitura válida é utilizada como referência.
    if pressao_anterior is None or ultima_pressao_aceita is None:

        ultima_pressao_aceita = instante_atual

    else:

        # Calcula o intervalo desde a última pressão aceita.
        tempo_decorrido = max(
            instante_atual - ultima_pressao_aceita,
            INTERVALO_MINIMO_PRESSAO
        )

        # Calcula a diferença absoluta entre as pressões.
        variacao = abs(
            novos_dados_validos["pressao"] - pressao_anterior
        )

        # Calcula a variação máxima permitida para o intervalo.
        variacao_permitida = (
            TAXA_MAXIMA_PRESSAO * tempo_decorrido
        )

        if variacao > variacao_permitida:

            # Preserva a última pressão aceita.
            dados_filtrados["pressao"] = pressao_anterior

            # Registra a diferença encontrada para diagnóstico.
            avisos.append(
                "Pressão preservada: variação de "
                f"{variacao:.2f} hPa em aproximadamente "
                f"{tempo_decorrido:.1f} s; limite calculado de "
                f"{variacao_permitida:.2f} hPa."
            )

        else:

            # Atualiza o instante quando a nova pressão é aceita.
            ultima_pressao_aceita = instante_atual

    # Retorna os dados filtrados e os avisos produzidos.
    return dados_filtrados, avisos


# ==========================================================
# ROTA DA DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    # Procura index.html dentro da pasta templates.
    return render_template("index.html")


# ==========================================================
# ROTA INICIAL DA API
# ==========================================================

@app.route("/")
def inicio():

    # Retorna uma mensagem JSON para indicar que a API está ativa.
    return jsonify({
        "mensagem": "API FUNCIONANDO."
    })


# ==========================================================
# ROTA DE RECEBIMENTO E CONSULTA DOS DADOS
# ==========================================================

@app.route("/dados", methods=["GET", "POST"])
def gerenciar_dados():

    # Permite atualizar as variáveis armazenadas no nível do módulo.
    global dados, ultima_atualizacao, avisos_validacao

    # ======================================================
    # RECEBIMENTO DE DADOS (POST)
    # ======================================================

    if request.method == "POST":

        # Converte o corpo JSON da requisição em um dicionário Python.
        # silent=True evita uma exceção quando o JSON recebido é inválido.
        novos_dados = request.get_json(silent=True)

        # Verifica se o conteúdo recebido é um objeto JSON válido.
        if not isinstance(novos_dados, dict):

            return jsonify({
                "erro": "Envie um objeto JSON válido."
            }), 400

        # Executa todas as validações dos campos recebidos.
        erros = validar_dados(novos_dados)

        # Rejeita o pacote quando alguma validação falha.
        if erros:

            return jsonify({
                "erro": "Dados inválidos.",
                "detalhes": erros
            }), 400

        # Seleciona somente os campos definidos no contrato da API.
        novos_dados_validos = {
            campo: novos_dados[campo]
            for campo in CAMPOS_OBRIGATORIOS
        }

        # Obtém um contador monotônico para medir o intervalo entre requisições.
        instante_atual = time.monotonic()

        # Aplica os filtros temporais de temperatura e pressão.
        dados_filtrados, avisos_validacao = filtrar_variacoes_temporais(
            novos_dados_validos,
            instante_atual
        )

        # Atualiza o armazenamento com os dados já processados.
        dados = dados_filtrados

        # Registra o horário de recebimento em UTC e formato ISO 8601.
        ultima_atualizacao = datetime.now(timezone.utc).isoformat()

        # Retorna a confirmação do recebimento e os dados processados.
        return jsonify({
            "mensagem": "Dados recebidos e processados com sucesso.",
            "dados": dados,
            "avisos_validacao": avisos_validacao,
            "ultima_atualizacao": ultima_atualizacao
        }), 200

    # ======================================================
    # CONSULTA DOS DADOS (GET)
    # ======================================================

    # Retorna a última medição armazenada sem modificar os valores.
    return jsonify({
        **dados,
        "ultima_atualizacao": ultima_atualizacao,
        "avisos_validacao": avisos_validacao
    })


# ==========================================================
# EXECUCAO LOCAL DA APLICACAO
# ==========================================================

if __name__ == "__main__":

    # Inicia o servidor Flask para execução local.
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )