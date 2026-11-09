
// ======================================================
// CONFIGURACOES GERAIS
// ======================================================

// Quantidade máxima de medições mantidas em cada gráfico.
const LIMITE_PONTOS = 60;
// Tempo máximo permitido sem receber uma nova medição.
// Após 5 segundos, a ESP32 será considerada sem atualização.
const TEMPO_MAXIMO_SEM_DADOS = 5000;


// Localização aproximada da estação meteorológica.
const LOCALIZACAO_ESTACAO = {
    latitude: -23.5505,
    longitude: -46.6333,
    zoom: 12
};


// Classificações aceitas para o indicador experimental.
const CLASSIFICACOES_QUALIDADE_AR = [
    "EXCELENTE",
    "BOA",
    "MODERADA",
    "RUIM",
    "PESSIMA"
];


// Guarda o horário da última medição registrada.
let ultimaAtualizacaoRecebida = null;


// Armazena temporariamente as medições recebidas.
const historico = {
    horarios: [],
    temperatura: [],
    umidade: [],
    pressao: [],
    adc_mq135: []
};


// Armazena as instâncias dos quatro gráficos.
const graficos = {};


// Impede consultas simultâneas à API.
let consultaEmAndamento = false;


// Referência ao elemento visual de alerta.
let elementoAlertaAr = null;


// ======================================================
// CRIACAO DOS GRAFICOS
// ======================================================

function criarGrafico(id, titulo, unidade, faixa, unidadeValor) {

    const canvas = document.getElementById(id);

    if (!canvas) {
        console.error("Canvas não encontrado:", id);
        return null;
    }

    return new Chart(canvas, {

        type: "line",

        data: {
            labels: [],

            datasets: [{
                label: titulo,
                data: [],

                borderColor: "#67e8f9",
                backgroundColor: "rgba(103, 232, 249, 0.12)",
                borderWidth: 2,
                tension: 0.25,
                fill: false,

                pointRadius: 2,
                pointHoverRadius: 5,
                pointBackgroundColor: "#67e8f9",
                pointBorderColor: "#070b16"
            }]
        },

        options: {

            responsive: true,
            maintainAspectRatio: false,
            animation: false,

            interaction: {
                mode: "index",
                intersect: false
            },

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
                    borderWidth: 1,

                    callbacks: {
                        label: function(context) {

                            const valor = Number(context.parsed.y);

                            return `${context.dataset.label}: ${valor.toFixed(2)} ${unidadeValor}`;
                        }
                    }
                }
            },

            scales: {

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

                y: {
                    suggestedMin: faixa.min,
                    suggestedMax: faixa.max,

                    title: {
                        display: true,
                        text: unidade,
                        color: "#94a3c4"
                    },

                    ticks: {
                        color: "#94a3c4",
                        maxTicksLimit: 6
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

function inicializarGraficos() {

    if (typeof Chart === "undefined") {
        console.error("A biblioteca Chart.js não foi carregada.");
        return false;
    }

    // Temperatura: 0 a 50 °C.
    graficos.temperatura = criarGrafico(
        "graficoTemperatura",
        "Temperatura",
        "Temperatura (°C)",
        {
            min: 0,
            max: 50
        },
        "°C"
    );

    // Umidade: 0 a 100%.
    graficos.umidade = criarGrafico(
        "graficoUmidade",
        "Umidade",
        "Umidade (%)",
        {
            min: 0,
            max: 100
        },
        "%"
    );

    // Pressão: 800 a 1100 hPa.
    graficos.pressao = criarGrafico(
        "graficoPressao",
        "Pressão",
        "Pressão (hPa)",
        {
            min: 800,
            max: 1100
        },
        "hPa"
    );

    // MQ-135: escala de referência do ADC da ESP32.
    graficos.adc_mq135 = criarGrafico(
        "graficoMQ135",
        "ADC MQ-135",
        "Valor ADC",
        {
            min: 0,
            max: 4095
        },
        "ADC"
    );

    return true;
}


// ======================================================
// INICIALIZACAO DO MAPA
// ======================================================

function inicializarMapa() {

    const elementoMapa = document.getElementById("mapa-estacao");
    const statusMapa = document.getElementById("mapa-status");

    if (!elementoMapa) {
        console.error("Elemento do mapa não encontrado.");
        return;
    }

    if (typeof L === "undefined") {

        console.error("A biblioteca Leaflet não foi carregada.");

        if (statusMapa) {
            statusMapa.textContent =
                "Não foi possível carregar o mapa. Verifique sua conexão com a internet.";
        }

        return;
    }

    const coordenadas = [
        LOCALIZACAO_ESTACAO.latitude,
        LOCALIZACAO_ESTACAO.longitude
    ];

    const mapa = L.map("mapa-estacao", {
        scrollWheelZoom: false
    }).setView(
        coordenadas,
        LOCALIZACAO_ESTACAO.zoom
    );

    // Adiciona os mapas do OpenStreetMap.
    L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,

            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }
    ).addTo(mapa);

    // Cria o marcador da estação.
    const marcador = L.marker(coordenadas).addTo(mapa);

    marcador.bindPopup(
        "<strong>Estação Meteorológica ESP32</strong><br>" +
        "Localização aproximada — São Paulo/SP"
    );

    if (statusMapa) {
        statusMapa.textContent =
            "Marcador em localização aproximada na região central de São Paulo - SP.";
    }

    console.log("Mapa inicializado com sucesso.");
}


// ======================================================
// INICIALIZACAO DO ELEMENTO DE ALERTA
// ======================================================

// Cria automaticamente a área de alerta logo abaixo
// do indicador de conexão com a API.
//
// Assim, não precisamos adicionar um novo elemento no HTML.

function inicializarAlertaQualidadeAr() {

    const status = document.getElementById("status");

    if (!status) {
        console.error("Elemento de status não encontrado.");
        return;
    }

    const alerta = document.createElement("div");

    alerta.id = "alerta-ar";
    alerta.className = "alerta-ar";

    // Informações de acessibilidade.
    alerta.setAttribute("role", "status");
    alerta.setAttribute("aria-live", "polite");

    // Inicialmente, o alerta fica escondido.
    alerta.hidden = true;

    // Insere a mensagem logo depois do status da API.
    status.insertAdjacentElement("afterend", alerta);

    elementoAlertaAr = alerta;
}


// ======================================================
// ATUALIZACAO DO ALERTA DE QUALIDADE DO AR
// ======================================================

// Recebe a classificação informada pela API.
//
// Atualiza a cor do indicador da qualidade do ar
// e apresenta mensagens quando necessário.

function atualizarAlertaQualidadeAr(qualidade) {

    const campoQualidade = document.getElementById("qualidade_ar");

    // Verifica se os elementos existem.
    if (!campoQualidade || !elementoAlertaAr) {
        return;
    }

    // Normaliza o texto recebido.
    const classificacao = String(qualidade ?? "")
        .trim()
        .toUpperCase();


    // --------------------------------------------------
    // 1. ATUALIZAR A COR DO INDICADOR
    // --------------------------------------------------

    // Remove as classificações anteriores.
    campoQualidade.classList.remove(
        "excelente",
        "boa",
        "moderada",
        "ruim",
        "pessima"
    );

    // Aplica uma classe somente quando a classificação
    // recebida estiver entre as opções permitidas.
    if (CLASSIFICACOES_QUALIDADE_AR.includes(classificacao)) {

        campoQualidade.classList.add(
            classificacao.toLowerCase()
        );
    }


    // --------------------------------------------------
    // 2. DEFINIR AS MENSAGENS DE ALERTA
    // --------------------------------------------------

    // As mensagens são baseadas nas faixas experimentais
    // utilizadas pelo projeto.

    const mensagens = {

        MODERADA:
            "Atenção: o indicador do MQ-135 está na faixa MODERADA. Continue acompanhando as medições.",

        RUIM:
            "Alerta: o indicador do MQ-135 está na faixa RUIM. Verifique as condições do ambiente.",

        PESSIMA:
            "Alerta: o indicador do MQ-135 está na faixa PÉSSIMA. Verifique o ambiente e acompanhe as leituras."
    };


    // Recupera a mensagem correspondente.
    const mensagem = mensagens[classificacao];


    // --------------------------------------------------
    // 3. EXIBIR OU ESCONDER O ALERTA
    // --------------------------------------------------

    // EXCELENTE e BOA não apresentam mensagem de alerta.
    if (!mensagem) {

        elementoAlertaAr.hidden = true;
        elementoAlertaAr.textContent = "";
        elementoAlertaAr.className = "alerta-ar";

        return;
    }

    // Aplica a mensagem e a aparência correspondente.
    elementoAlertaAr.textContent = mensagem;

    elementoAlertaAr.className =
        "alerta-ar " + classificacao.toLowerCase();

    elementoAlertaAr.hidden = false;
}


// ======================================================
// REGISTRO DE UMA NOVA MEDICAO NOS GRAFICOS
// ======================================================

function registrarMedicao(dados) {

    const horario = dados.ultima_atualizacao;

    if (!horario) {
        return;
    }

    // Ignora medições que já foram registradas.
    if (horario === ultimaAtualizacaoRecebida) {
        return;
    }

    const data = new Date(horario);

    if (Number.isNaN(data.getTime())) {

        console.error("Horário inválido recebido da API:", horario);
        return;
    }


    // --------------------------------------------------
    // VALIDACAO DOS VALORES DOS SENSORES
    // --------------------------------------------------

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

        valores[chave] = Number(Number(valor).toFixed(2));
    }


    // Atualiza a referência da última medição registrada.
    ultimaAtualizacaoRecebida = horario;


    // Formata o horário para apresentação.
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

    Object.keys(graficos).forEach(chave => {

        const grafico = graficos[chave];

        if (!grafico) {
            return;
        }

        grafico.data.labels = [...historico.horarios];

        grafico.data.datasets[0].data = [...historico[chave]];

        grafico.update("none");
    });
}


// ======================================================
// FUNCAO AUXILIAR PARA ATUALIZAR OS CARTOES
// ======================================================

function atualizarElemento(id, valor, casasDecimais = null) {

    const elemento = document.getElementById(id);

    if (!elemento) {
        console.error("Elemento HTML não encontrado:", id);
        return;
    }

    if (valor === null || valor === undefined) {

        elemento.textContent = "--";
        return;
    }

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
// ATUALIZACAO VISUAL DO STATUS DA API
// ======================================================

function atualizarStatus(tipo, mensagem) {

    const status = document.getElementById("status");

    if (!status) {
        return;
    }

    status.textContent = mensagem;

    status.classList.remove("ok", "erro");

    if (tipo) {
        status.classList.add(tipo);
    }
}
// ======================================================
// VERIFICACAO DO STATUS DA ESTACAO ESP32
// ======================================================

function atualizarStatusEstacao(ultimaAtualizacao) {

    // Verifica se a API já recebeu alguma medição.
    if (!ultimaAtualizacao) {

        atualizarStatus(
            "erro",
            "API conectada • aguardando primeira leitura da ESP32"
        );

        return;
    }


    // Converte o horário recebido da API para uma data.
    const dataUltimaAtualizacao = new Date(ultimaAtualizacao);


    // Verifica se o horário recebido é válido.
    if (Number.isNaN(dataUltimaAtualizacao.getTime())) {

        atualizarStatus(
            "erro",
            "API conectada • horário da última leitura inválido"
        );

        return;
    }


    // Calcula quanto tempo passou desde a última medição.
    // O Math.max evita uma idade negativa caso haja
    // uma pequena diferença entre os relógios.
    const idadeMs = Math.max(
        0,
        Date.now() - dataUltimaAtualizacao.getTime()
    );


    // Se a medição foi recebida nos últimos 5 segundos,
    // consideramos que a ESP32 está enviando normalmente.
    if (idadeMs <= TEMPO_MAXIMO_SEM_DADOS) {

        atualizarStatus(
            "ok",
            "ESP32 enviando dados • API conectada"
        );

        return;
    }


    // Caso contrário, calcula há quantos segundos
    // não recebemos uma nova medição.
    const segundos = Math.floor(idadeMs / 1000);


    // A API continua acessível, mas a estação
    // não está enviando medições recentes.
    atualizarStatus(
        "erro",
        `API conectada • ESP32 sem atualização há ${segundos}s`
    );
}


// ======================================================
// FUNCAO RESPONSAVEL POR ATUALIZAR A DASHBOARD
// ======================================================

async function atualizarDados() {

    // Evita consultas simultâneas.
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

        if (!resposta.ok) {
            throw new Error("Erro HTTP: " + resposta.status);
        }

        const dados = await resposta.json();


        // --------------------------------------------------
        // 2. ATUALIZACAO DOS CARTOES
        // --------------------------------------------------

        atualizarElemento(
            "temperatura",
            dados.temperatura,
            2
        );

        atualizarElemento(
            "umidade",
            dados.umidade,
            2
        );

        atualizarElemento(
            "pressao",
            dados.pressao,
            2
        );

        // O LDR permanece como leitura digital 0 ou 1.
        atualizarElemento(
            "luminosidade",
            dados.luminosidade
        );

        atualizarElemento(
            "adc_mq135",
            dados.adc_mq135,
            2
        );

        atualizarElemento(
            "qualidade_ar",
            dados.qualidade_ar
        );


        // --------------------------------------------------
        // 3. ATUALIZACAO DO ALERTA
        // --------------------------------------------------

        atualizarAlertaQualidadeAr(dados.qualidade_ar);


        // --------------------------------------------------
        // 4. REGISTRO DA MEDICAO NOS GRAFICOS
        // --------------------------------------------------

        registrarMedicao(dados);


// --------------------------------------------------
// 5. ATUALIZACAO DO STATUS
// --------------------------------------------------

atualizarStatusEstacao(dados.ultima_atualizacao);

    } catch (erro) {

        atualizarStatus(
            "erro",
            "Falha ao carregar os dados. Tentando novamente..."
        );

        console.error("Erro ao consultar a API:", erro);

    } finally {

        consultaEmAndamento = false;
    }
}


// ======================================================
// INICIALIZACAO DO SISTEMA
// ======================================================

// Inicializa os gráficos.
inicializarGraficos();

// Inicializa o mapa.
inicializarMapa();

// Cria a área de alerta da qualidade do ar.
inicializarAlertaQualidadeAr();

// Realiza a primeira consulta à API.
atualizarDados();

// Continua consultando a API a cada segundo.
setInterval(atualizarDados, 1000);
