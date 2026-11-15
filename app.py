# ==========================================================
# IMPORTACAO DAS BIBLIOTECAS
# ==========================================================

# Flask fornece a estrutura da aplicação web.
# Flask cria a aplicação; jsonify gera respostas JSON; request lê o corpo
# da requisição; render_template carrega a página HTML da dashboard.
from flask import Flask, jsonify, request, render_template

# datetime e timezone geram o horário da última atualização em formato UTC.
from datetime import datetime, timezone

# math permite verificar se os números recebidos são finitos.
import math

# time.monotonic mede intervalos de tempo sem depender do relógio do sistema.
import time


# ==========================================================
# INICIALIZACAO DA APLICACAO
# ==========================================================

# Cria a aplicação Flask. O objeto app será utilizado para registrar as rotas.
app = Flask(__name__)


# ==========================================================
# CAMPOS E CLASSIFICACOES DA API
# ==========================================================

# Define os campos que a ESP32 precisa enviar em cada pacote JSON.
# adc_mq135 é mantido como leitura bruta para diagnóstico; a classificação
# apresentada ao usuário é calculada a partir de ppm.
CAMPOS_OBRIGATORIOS = (
    "temperatura",
    "umidade",
    "pressao",
    "luminosidade",
    "adc_mq135",
    "ppm",
    "indicador_ppm_estimado",
)

# Lista os valores de classificação aceitos para o indicador de PPM.
# LEITURA_INVALIDA é utilizado quando a ESP32 não consegue calcular ppm.
CLASSIFICACOES_PPM = (
    "EXCELENTE",
    "BOA",
    "MODERADA",
    "RUIM",
    "PESSIMA",
    "LEITURA_INVALIDA",
)

# Define a faixa máxima de variação de temperatura permitida por segundo.
TAXA_MAXIMA_TEMPERATURA = 1.0

# Define o menor intervalo considerado pelo filtro da temperatura.
# Esse limite evita calcular uma taxa usando um intervalo excessivamente curto.
INTERVALO_MINIMO_TEMPERATURA = 2.0

# Define a faixa máxima de variação de pressão permitida por segundo.
TAXA_MAXIMA_PRESSAO = 0.5

# Define o menor intervalo considerado pelo filtro da pressão.
INTERVALO_MINIMO_PRESSAO = 1.0


# ==========================================================
# ARMAZENAMENTO DOS DADOS DOS SENSORES
# ==========================================================

# Guarda a última medição aceita de cada sensor.
# None indica que a API ainda não recebeu uma medição para aquele campo.
# Os dados ficam em memória e não são preservados se o processo da API reiniciar.
dados = {
    "temperatura": None,
    "umidade": None,
    "pressao": None,
    "luminosidade": None,
    "adc_mq135": None,
    "ppm": None,
    "indicador_ppm_estimado": None,
}

# Armazena o horário UTC em que o último pacote válido foi recebido.
# O valor começa como None porque ainda não houve recebimento.
ultima_atualizacao = None

# Guarda o instante monotônico em que a última temperatura aceita foi recebida.
# É usado para calcular quanto tempo passou entre temperaturas aceitas.
ultima_temperatura_aceita = None

# Guarda o instante monotônico em que a última pressão aceita foi recebida.
# É usado para calcular quanto tempo passou entre pressões aceitas.
ultima_pressao_aceita = None

# Armazena avisos produzidos pelo filtro temporal no pacote mais recente.
avisos_validacao = []


# ==========================================================
# FUNCOES AUXILIARES
# ==========================================================

def numero_valido(valor):
    # JSON pode representar números, mas também podemos receber texto,
    # valores booleanos ou números não finitos. Esses casos não são medições válidas.
    # Em Python, bool herda de int; por isso é excluído explicitamente.
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(valor)
    )


def classificar_indicador_ppm(valor):
    # Compara o valor recebido com as faixas usadas no firmware.
    # A primeira condição verdadeira define a classificação retornada.
    if valor <= 100:
        return "EXCELENTE"
    if valor <= 200:
        return "BOA"
    if valor <= 500:
        return "MODERADA"
    if valor <= 1000:
        return "RUIM"
    return "PESSIMA"


# ==========================================================
# VALIDACAO DOS DADOS RECEBIDOS
# ==========================================================

def validar_dados(novos_dados):
    # Acumula todos os problemas encontrados para retornar uma única resposta
    # com os campos que precisam ser corrigidos.
    erros = []

    # Confere se o pacote contém todos os campos exigidos pela API.
    # A compreensão de lista reúne os nomes dos campos ausentes.
    campos_faltantes = [
        campo for campo in CAMPOS_OBRIGATORIOS
        if campo not in novos_dados
    ]

    # Acrescenta uma mensagem para cada campo que não foi enviado.
    for campo in campos_faltantes:
        erros.append(f"O campo '{campo}' não foi enviado.")

    # ------------------------------------------------------
    # 1. VALIDACAO DA TEMPERATURA
    # ------------------------------------------------------

    # Obtém a temperatura enviada pelo DHT22.
    temperatura = novos_dados.get("temperatura")

    # Primeiro verifica o tipo e se o número é finito; depois verifica a faixa.
    if not numero_valido(temperatura):
        erros.append("Temperatura inválida. Envie um número finito.")
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

    # A umidade relativa é expressa em porcentagem e não pode sair de 0 a 100.
    if not numero_valido(umidade):
        erros.append("Umidade inválida. Envie um número finito.")
    elif not 0 <= umidade <= 100:
        erros.append(
            "Umidade fora da faixa permitida: "
            "utilize valores entre 0 e 100%."
        )

    # ------------------------------------------------------
    # 3. VALIDACAO DA PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    # Obtém a pressão enviada pelo BMP280, já convertida para hPa e ajustada
    # pelo offset aplicado no firmware da ESP32.
    pressao = novos_dados.get("pressao")

    # A faixa evita aceitar valores incompatíveis com uma leitura atmosférica
    # plausível para o sensor e a aplicação.
    if not numero_valido(pressao):
        erros.append("Pressão inválida. Envie um número finito.")
    elif not 300 <= pressao <= 1100:
        erros.append(
            "Pressão fora da faixa permitida: "
            "utilize valores entre 300 e 1100 hPa."
        )

    # ------------------------------------------------------
    # 4. VALIDACAO DA LUMINOSIDADE
    # ------------------------------------------------------

    # O módulo LDR está conectado pela saída digital DO.
    luminosidade = novos_dados.get("luminosidade")

    # Aceita somente os inteiros 0 e 1. O teste de bool é necessário porque
    # True e False também são considerados inteiros pelo Python.
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

    # Mantém a leitura bruta do ADC para diagnóstico, mesmo que a classificação
    # principal do ar seja baseada no campo ppm.
    adc = novos_dados.get("adc_mq135")

    # O ADC de 12 bits da ESP32 retorna valores entre 0 e 4095.
    if not numero_valido(adc):
        erros.append("ADC do MQ-135 inválido. Envie um número finito.")
    elif not 0 <= adc <= 4095:
        erros.append(
            "ADC do MQ-135 fora da faixa permitida: "
            "utilize valores entre 0 e 4095."
        )

    # ------------------------------------------------------
    # 6. VALIDACAO DO PPM E DO INDICADOR
    # ------------------------------------------------------

    # Obtém os dois campos calculados pelo firmware.
    ppm = novos_dados.get("ppm")
    indicador_ppm = novos_dados.get("indicador_ppm_estimado")

    # Quando o cálculo de ppm falha, o firmware deve enviar None junto
    # com o indicador LEITURA_INVALIDA. Nos demais casos, ppm deve ser numérico.
    if ppm is None:
        if indicador_ppm != "LEITURA_INVALIDA":
            erros.append(
                "Quando 'ppm' for nulo, "
                "'indicador_ppm_estimado' deve ser LEITURA_INVALIDA."
            )
    elif not numero_valido(ppm):
        erros.append("PPM inválido. Envie um número finito ou null.")
    elif not 0 <= ppm <= 1_000_000:
        erros.append(
            "PPM fora da faixa permitida: "
            "utilize valores entre 0 e 1.000.000."
        )

    # Confere se o indicador pertence à lista de classificações aceitas.
    if (
        not isinstance(indicador_ppm, str)
        or indicador_ppm not in CLASSIFICACOES_PPM
    ):
        erros.append(
            "Indicador PPM inválido. Utilize EXCELENTE, BOA, MODERADA, "
            "RUIM, PESSIMA ou LEITURA_INVALIDA."
        )
    # Se ppm for um número válido, compara a classificação enviada com a faixa
    # calculada novamente pela API. Isso evita receber pares incompatíveis.
    elif numero_valido(ppm):
        indicador_esperado = classificar_indicador_ppm(ppm)

        if indicador_ppm != indicador_esperado:
            erros.append(
                "Indicador PPM incompatível com o valor enviado. "
                f"Para {ppm} ppm, o resultado esperado é {indicador_esperado}."
            )

    # Retorna a lista vazia quando todos os campos passaram pelas validações.
    return erros


# ==========================================================
# FILTRO DE VARIACOES TEMPORAIS
# ==========================================================

def filtrar_variacoes_temporais(novos_dados_validos, instante_atual):
    # As duas variáveis globais guardam o momento em que cada tipo de leitura
    # foi aceito pela última vez.
    global ultima_temperatura_aceita, ultima_pressao_aceita

    # Copia o pacote para que seja possível preservar uma medição anterior
    # sem modificar o objeto recebido originalmente.
    dados_filtrados = novos_dados_validos.copy()

    # Reúne mensagens quando uma variação ultrapassa o limite configurado.
    avisos = []

    # ------------------------------------------------------
    # 1. FILTRO DA TEMPERATURA
    # ------------------------------------------------------

    # Recupera a última temperatura armazenada pela API.
    temperatura_anterior = dados["temperatura"]

    # Na primeira medição, não existe valor anterior para comparar.
    # Por isso, ela é aceita como referência inicial.
    if temperatura_anterior is None or ultima_temperatura_aceita is None:
        ultima_temperatura_aceita = instante_atual
    else:
        # Calcula o tempo desde a última temperatura aceita.
        # max() garante o intervalo mínimo configurado, mesmo que as requisições
        # cheguem em uma sequência mais rápida que o esperado.
        tempo_decorrido = max(
            instante_atual - ultima_temperatura_aceita,
            INTERVALO_MINIMO_TEMPERATURA,
        )

        # Calcula a diferença absoluta entre a temperatura nova e a anterior.
        variacao = abs(
            novos_dados_validos["temperatura"] - temperatura_anterior
        )

        # Multiplica a taxa máxima pelo tempo para determinar a diferença
        # que o filtro considera aceitável nesse intervalo.
        variacao_permitida = TAXA_MAXIMA_TEMPERATURA * tempo_decorrido

        if variacao > variacao_permitida:
            # Preserva a última temperatura aceita quando a variação é maior
            # que o limite calculado. Os outros sensores continuam atualizando.
            dados_filtrados["temperatura"] = temperatura_anterior

            # Registra a diferença observada e o limite para diagnóstico.
            avisos.append(
                "Temperatura preservada: variação de "
                f"{variacao:.2f} °C em aproximadamente {tempo_decorrido:.1f} s; "
                f"limite calculado de {variacao_permitida:.2f} °C."
            )

            # Não atualiza o instante da última leitura aceita. Assim, se a nova
            # temperatura persistir, o limite permitido aumenta com o tempo.
        else:
            # Atualiza o instante quando a nova temperatura é aceita.
            ultima_temperatura_aceita = instante_atual

    # ------------------------------------------------------
    # 2. FILTRO DA PRESSAO ATMOSFERICA
    # ------------------------------------------------------

    # Recupera a última pressão armazenada pela API.
    pressao_anterior = dados["pressao"]

    # A primeira pressão recebida é aceita porque ainda não existe referência.
    if pressao_anterior is None or ultima_pressao_aceita is None:
        ultima_pressao_aceita = instante_atual
    else:
        # Calcula o intervalo desde a última pressão aceita, respeitando
        # o intervalo mínimo definido nas configurações.
        tempo_decorrido = max(
            instante_atual - ultima_pressao_aceita,
            INTERVALO_MINIMO_PRESSAO,
        )

        # Calcula quanto a pressão mudou desde a última medição aceita.
        variacao = abs(
            novos_dados_validos["pressao"] - pressao_anterior
        )

        # Determina a variação máxima permitida para o intervalo decorrido.
        variacao_permitida = TAXA_MAXIMA_PRESSAO * tempo_decorrido

        if variacao > variacao_permitida:
            # Mantém a pressão anterior se a mudança for maior que o limite.
            dados_filtrados["pressao"] = pressao_anterior

            # Guarda um aviso que poderá ser consultado no GET /dados.
            avisos.append(
                "Pressão preservada: variação de "
                f"{variacao:.2f} hPa em aproximadamente {tempo_decorrido:.1f} s; "
                f"limite calculado de {variacao_permitida:.2f} hPa."
            )

            # O instante da última pressão aceita não é alterado nesta condição.
        else:
            # Atualiza o instante quando a nova pressão passa pelo filtro.
            ultima_pressao_aceita = instante_atual

    # Retorna o pacote após os filtros e os avisos produzidos nesta medição.
    return dados_filtrados, avisos


# ==========================================================
# ROTA DA DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():
    # render_template procura index.html dentro da pasta templates.
    return render_template("index.html")


# ==========================================================
# ROTA INICIAL DA API
# ==========================================================

@app.route("/")
def inicio():
    # Retorna uma mensagem JSON simples para indicar que a aplicação está ativa.
    return jsonify({"mensagem": "API FUNCIONANDO."})


# ==========================================================
# ROTA DE RECEBIMENTO E CONSULTA DOS DADOS
# ==========================================================

# GET consulta a última medição armazenada; POST recebe uma nova medição da ESP32.
@app.route("/dados", methods=["GET", "POST"])
def gerenciar_dados():
    # Atribuições a estas variáveis alteram os objetos armazenados no nível do módulo.
    global dados, ultima_atualizacao, avisos_validacao

    if request.method == "POST":
        # Converte o corpo da requisição JSON em um dicionário Python.
        # silent=True evita que um JSON inválido gere uma exceção não tratada.
        novos_dados = request.get_json(silent=True)

        # A API espera receber um objeto JSON, representado por um dicionário.
        if not isinstance(novos_dados, dict):
            return jsonify({"erro": "Envie um objeto JSON válido."}), 400

        # Executa as verificações de presença, tipo, faixa e coerência dos campos.
        erros = validar_dados(novos_dados)

        # HTTP 400 informa que o pacote recebido não atende ao contrato da API.
        # Os dados armazenados anteriormente não são substituídos nesse caso.
        if erros:
            return jsonify({"erro": "Dados inválidos.", "detalhes": erros}), 400

        # Copia somente os campos definidos no contrato da API.
        # Qualquer campo adicional enviado pela ESP32 é ignorado.
        novos_dados_validos = {
            campo: novos_dados[campo]
            for campo in CAMPOS_OBRIGATORIOS
        }

        # Obtém o tempo monotônico para medir intervalos entre requisições.
        # Ao contrário do horário civil, esse contador não depende de ajustes
        # de data e hora do sistema operacional.
        instante_atual = time.monotonic()

        # Aplica os filtros de variação à temperatura e à pressão.
        # Os outros campos permanecem com os valores recebidos e validados.
        dados_filtrados, avisos_validacao = filtrar_variacoes_temporais(
            novos_dados_validos,
            instante_atual,
        )

        # Substitui o conjunto armazenado pelo pacote já filtrado.
        dados = dados_filtrados

        # Registra o horário real de recebimento em UTC e formato ISO 8601.
        # O JavaScript da dashboard consegue converter esse texto para Date.
        ultima_atualizacao = datetime.now(timezone.utc).isoformat()

        # Retorna confirmação, dados processados, avisos e horário ao remetente.
        return jsonify({
            "mensagem": "Dados recebidos e processados com sucesso.",
            "dados": dados,
            "avisos_validacao": avisos_validacao,
            "ultima_atualizacao": ultima_atualizacao,
        }), 200

    # Para GET, devolve a última medição armazenada sem alterar os dados.
    # Se a API ainda não recebeu um POST, os valores permanecem None.
    return jsonify({
        **dados,
        "ultima_atualizacao": ultima_atualizacao,
        "avisos_validacao": avisos_validacao,
    })


# ==========================================================
# EXECUCAO LOCAL DA APLICACAO
# ==========================================================

if __name__ == "__main__":
    # Inicia o servidor para execução local. O Render utiliza o comando
    # de inicialização configurado no próprio serviço, não este bloco.
    app.run(host="0.0.0.0", port=5000, debug=False)
