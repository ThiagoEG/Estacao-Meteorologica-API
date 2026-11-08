
// ======================================================
// CONFIGURACOES DOS GRAFICOS
// ======================================================

// Quantidade máxima de medições mantidas em cada gráfico.
// Ao receber a 61ª amostra, a mais antiga será removida.
const LIMITE_PONTOS = 60;


// Guarda o horário da última medição registrada.
// É utilizado para evitar adicionar o mesmo envio
// várias vezes ao histórico.
let ultimaAtualizacaoRecebida = null;


// Armazena temporariamente as medições recebidas pela dashboard.
// Os dados ficam na memória do navegador e não são permanentes.
const historico = {
    horarios: [],
    temperatura: [],
    umidade: [],
    pressao: [],
    adc_mq135: []
};


// Armazena as instâncias dos quatro gráficos.
const graficos = {};


// Impede que uma nova consulta comece antes que a anterior
// tenha terminado.
let consultaEmAndamento = false;


// ======================================================
// CRIACAO DOS GRAFICOS
// ======================================================

// Cria um gráfico de linhas utilizando Chart.js.
//
// id: identificador do canvas no HTML.
// titulo: nome da informação apresentada.
// unidade: unidade utilizada no eixo vertical.

function criarGrafico(id, titulo, unidade) {

    // Localiza no HTML o canvas onde o gráfico será desenhado.
    const canvas = document.getElementById(id);

    // Verifica se o elemento existe antes de criar o gráfico.
    if (!canvas) {
        console.error("Canvas não encontrado:", id);
        return null;
    }

    // Cria e retorna uma nova instância do Chart.js.
    return new Chart(canvas, {

        // Define o gráfico como gráfico de linhas.
        type: "line",

        // Configura os dados inicialmente vazios.
        data: {
            labels: [],

            datasets: [{
                label: titulo,
                data: [],

                // Cor da linha e dos pontos.
                borderColor: "#67e8f9",
                backgroundColor: "rgba(103, 232, 249, 0.12)",

                // Espessura da linha.
                borderWidth: 2,

                // Suaviza visualmente a linha.
                tension: 0.25,

                // Mantém a linha sem preenchimento abaixo.
                fill: false,

                // Aparência dos pontos de medição.
                pointRadius: 2,
                pointHoverRadius: 5,
                pointBackgroundColor: "#67e8f9",
                pointBorderColor: "#070b16"
            }]
        },

        // Configurações de apresentação e comportamento.
        options: {

            // Ajusta o gráfico ao tamanho do seu contêiner.
            responsive: true,
            maintainAspectRatio: false,

            // Evita animações a cada atualização.
            animation: false,

            // Permite visualizar informações relacionadas
            // ao mesmo instante ao passar o mouse pelo gráfico.
            interaction: {
                mode: "index",
                intersect: false
            },

            // Configura legenda e informações ao passar o mouse.
            plugins: {

                legend: {
                    display: true,

                    labels: {
                        color: "#f1f5ff",
                        usePointStyle: true
                    }
                },

                tooltip: {
                    backgroundColor: "#111827",
                    titleColor: "#ffffff",
                    bodyColor: "#f1f5ff",
                    borderColor: "rgba(255, 255, 255, 0.14)",
                    borderWidth: 1
                }
            },

            // Configuração dos eixos.
            scales: {

                // Eixo horizontal: horário das medições.
                x: {
                    title: {
                        display: true,
                        text: "Horário",
                        color: "#94a3c4"
                    },

                    ticks: {
                        color: "#94a3c4",
                        maxTicksLimit: 6
                    },

                    grid: {
                        color: "rgba(255, 255, 255, 0.07)"
                    }
                },

                // Eixo vertical: valor do sensor.
                y: {
                    title: {
                        display: true,
                        text: unidade,
                        color: "#94a3c4"
                    },

                    ticks: {
                        color: "#94a3c4"
                    },

                    grid: {
                        color: "rgba(255, 255, 255, 0.07)"
                    }
                }
            }
        }
    });
}


// ======================================================
// INICIALIZACAO DOS QUATRO GRAFICOS
// ======================================================

// Cria os gráficos depois que o HTML estiver disponível.

function inicializarGraficos() {

    // Verifica se a biblioteca Chart.js foi carregada.
    if (typeof Chart === "undefined") {
        console.error("A biblioteca Chart.js não foi carregada.");
        return false;
    }

    // Gráfico de temperatura em graus Celsius.
    graficos.temperatura = criarGrafico(
        "graficoTemperatura",
        "Temperatura",
        "Temperatura (°C)"
    );

    // Gráfico de umidade relativa do ar.
    graficos.umidade = criarGrafico(
        "graficoUmidade",
        "Umidade",
        "Umidade (%)"
    );

    // Gráfico de pressão atmosférica.
    graficos.pressao = criarGrafico(
        "graficoPressao",
        "Pressão",
        "Pressão (hPa)"
    );

    // Gráfico das leituras ADC do MQ-135.
    graficos.adc_mq135 = criarGrafico(
        "graficoMQ135",
        "ADC MQ-135",
        "Valor ADC"
    );

    return true;
}


// ======================================================
// REGISTRO DE UMA NOVA MEDICAO NOS GRAFICOS
// ======================================================

// Recebe os dados da API e adiciona uma nova amostra
// ao histórico dos gráficos.
//
// O horário da API identifica uma nova medição.
// Assim, consultas GET repetidas não criam pontos duplicados.

function registrarMedicao(dados) {

    const horario = dados.ultima_atualizacao;

    // Se a API ainda não forneceu um horário,
    // não registra a amostra.
    if (!horario) {
        return;
    }

    // Ignora medições que já foram registradas.
    if (horario === ultimaAtualizacaoRecebida) {
        return;
    }

    // Converte o horário recebido em um objeto Date.
    const data = new Date(horario);

    // Verifica se o horário recebido é válido.
    if (Number.isNaN(data.getTime())) {
        console.error("Horário inválido recebido da API:", horario);
        return;
    }


    // --------------------------------------------------
    // VALIDACAO DOS VALORES DOS SENSORES
    // --------------------------------------------------

    // Converte os valores para números e verifica
    // se todos os campos necessários para os gráficos
    // possuem valores válidos.

    const chaves = [
        "temperatura",
        "umidade",
        "pressao",
        "adc_mq135"
    ];

    const valores = {};

    for (const chave of chaves) {

        const valor = dados[chave];

        if (
            valor === null ||
            valor === undefined ||
            !Number.isFinite(Number(valor))
        ) {

            console.error(
                "Valor inválido recebido para o gráfico:",
                chave,
                valor
            );

            return;
        }

        valores[chave] = Number(valor);
    }


    // Atualiza a referência da última medição registrada.
    // Isso acontece somente depois de validar os dados.
    ultimaAtualizacaoRecebida = horario;


    // Formata o horário para apresentação nos gráficos.
    const horarioFormatado = data.toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });


    // --------------------------------------------------
    // ADICIONAR OS VALORES AO HISTORICO
    // --------------------------------------------------

    historico.horarios.push(horarioFormatado);

    historico.temperatura.push(valores.temperatura);

    historico.umidade.push(valores.umidade);

    historico.pressao.push(valores.pressao);

    historico.adc_mq135.push(valores.adc_mq135);


    // --------------------------------------------------
    // LIMITAR A QUANTIDADE DE MEDICOES
    // --------------------------------------------------

    // Quando o limite de 60 amostras for ultrapassado,
    // remove o registro mais antigo de todos os históricos.

    if (historico.horarios.length > LIMITE_PONTOS) {

        historico.horarios.shift();
        historico.temperatura.shift();
        historico.umidade.shift();
        historico.pressao.shift();
        historico.adc_mq135.shift();
    }


    // --------------------------------------------------
    // ATUALIZAR OS GRAFICOS
    // --------------------------------------------------

    // Percorre os quatro gráficos e atualiza seus dados.

    Object.keys(graficos).forEach(chave => {

        const grafico = graficos[chave];

        // Ignora gráficos que não foram inicializados.
        if (!grafico) {
            return;
        }

        // Atualiza os horários do eixo horizontal.
        grafico.data.labels = [...historico.horarios];

        // Atualiza os valores do eixo vertical.
        grafico.data.datasets[0].data = [...historico[chave]];

        // Atualiza o gráfico sem animações.
        grafico.update("none");
    });
}


// ======================================================
// FUNCAO AUXILIAR PARA ATUALIZAR OS CARTOES
// ======================================================

// Localiza um elemento HTML e atualiza seu conteúdo.
//
// Quando o valor não estiver disponível, apresenta "--".
// O parâmetro casasDecimais permite formatar valores numéricos.

function atualizarElemento(id, valor, casasDecimais = null) {

    const elemento = document.getElementById(id);

    if (!elemento) {
        console.error("Elemento HTML não encontrado:", id);
        return;
    }

    // Verifica se o valor está disponível.
    if (valor === null || valor === undefined) {

        elemento.textContent = "--";
        return;
    }

    // Formata valores numéricos quando solicitado.
    if (casasDecimais !== null) {

        const numero = Number(valor);

        elemento.textContent = Number.isFinite(numero)
            ? numero.toFixed(casasDecimais)
            : "--";

        return;
    }

    elemento.textContent = valor;
}


// ======================================================
// ATUALIZACAO VISUAL DO STATUS
// ======================================================

// Atualiza a mensagem e a aparência do indicador de conexão.
// As classes utilizadas já estão definidas no style.css.

function atualizarStatus(tipo, mensagem) {

    const status = document.getElementById("status");

    if (!status) {
        return;
    }

    status.textContent = mensagem;

    // Remove os estados anteriores.
    status.classList.remove("ok", "erro");

    // Aplica o novo estado.
    if (tipo) {
        status.classList.add(tipo);
    }
}


// ======================================================
// FUNCAO RESPONSAVEL POR ATUALIZAR A DASHBOARD
// ======================================================

async function atualizarDados() {

    // Evita consultas simultâneas caso uma requisição
    // demore mais de um segundo para terminar.
    if (consultaEmAndamento) {
        return;
    }

    consultaEmAndamento = true;

    try {

        // --------------------------------------------------
        // 1. CONSULTA A API
        // --------------------------------------------------

        const resposta = await fetch("/dados", {
            cache: "no-store"
        });

        // Verifica se o servidor retornou uma resposta válida.
        if (!resposta.ok) {
            throw new Error("Erro HTTP: " + resposta.status);
        }

        // Converte o JSON recebido para um objeto JavaScript.
        const dados = await resposta.json();


        // --------------------------------------------------
        // 2. ATUALIZACAO DOS CARTOES
        // --------------------------------------------------

        atualizarElemento(
            "temperatura",
            dados.temperatura
        );

        atualizarElemento(
            "umidade",
            dados.umidade
        );

        // Pressão com duas casas decimais.
        // A unidade hPa já está definida no HTML.
        atualizarElemento(
            "pressao",
            dados.pressao,
            2
        );

        // Luminosidade digital do LDR.
        atualizarElemento(
            "luminosidade",
            dados.luminosidade
        );

        // ADC do MQ-135 com uma casa decimal.
        atualizarElemento(
            "adc_mq135",
            dados.adc_mq135,
            1
        );

        // Classificação experimental da qualidade do ar.
        atualizarElemento(
            "qualidade_ar",
            dados.qualidade_ar
        );


        // --------------------------------------------------
        // 3. REGISTRO DA MEDICAO NOS GRAFICOS
        // --------------------------------------------------

        // Adiciona um ponto somente quando a API informar
        // que uma nova medição foi recebida.
        registrarMedicao(dados);


        // --------------------------------------------------
        // 4. ATUALIZACAO DO STATUS
        // --------------------------------------------------

        atualizarStatus(
            "ok",
            "Conectado à API"
        );


    } catch (erro) {

        // Apresenta uma mensagem caso a consulta falhe.
        atualizarStatus(
            "erro",
            "Falha ao carregar os dados. Tentando novamente..."
        );

        // Registra os detalhes do erro no console.
        console.error("Erro ao consultar a API:", erro);

    } finally {

        // Libera a próxima consulta, independentemente
        // de a operação ter sido concluída com sucesso ou erro.
        consultaEmAndamento = false;
    }
}


// ======================================================
// INICIALIZACAO DO SISTEMA
// ======================================================

// Primeiro cria os gráficos nos elementos canvas do HTML.
inicializarGraficos();

// Em seguida, realiza a primeira consulta à API.
atualizarDados();

// Continua consultando a API a cada segundo.
setInterval(atualizarDados, 1000);
