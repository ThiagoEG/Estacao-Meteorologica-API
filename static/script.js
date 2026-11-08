
// ======================================================
// CONFIGURACOES GERAIS
// ======================================================

// Quantidade máxima de medições mantidas em cada gráfico.
const LIMITE_PONTOS = 60;


// Localização aproximada da estação meteorológica.
//
// Coordenadas de referência da região central de São Paulo.
// Não representam o endereço exato do equipamento.
const LOCALIZACAO_ESTACAO = {
    latitude: -23.5505,
    longitude: -46.6333,
    zoom: 12
};


// Guarda o horário da última medição registrada.
let ultimaAtualizacaoRecebida = null;


// Armazena temporariamente as medições recebidas pela dashboard.
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

                    // Exibe os valores com duas casas decimais.
                    callbacks: {
                        label: function(context) {

                            const valor = Number(context.parsed.y);

                            return `${context.dataset.label}: ${valor.toFixed(2)} ${unidadeValor}`;
                        }
                    }
                }
            },

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

                    // Faixas de referência para evitar oscilações
                    // visuais exageradas em pequenas variações.
                    //
                    // Os limites sugeridos podem ser ampliados
                    // automaticamente se os dados saírem da faixa.
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

    // Temperatura: referência de 0 a 50 °C.
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

    // Umidade: faixa física de 0 a 100%.
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

    // Pressão: referência de 800 a 1100 hPa.
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

    // MQ-135: utiliza toda a faixa do ADC da ESP32.
    // Isso permite visualizar picos acima de 1500.
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

    // Verifica se o elemento do mapa existe no HTML.
    if (!elementoMapa) {
        console.error("Elemento do mapa não encontrado.");
        return;
    }

    // Verifica se a biblioteca Leaflet foi carregada.
    if (typeof L === "undefined") {

        console.error("A biblioteca Leaflet não foi carregada.");

        if (statusMapa) {
            statusMapa.textContent =
                "Não foi possível carregar o mapa. Verifique sua conexão com a internet.";
        }

        return;
    }


    // Organiza as coordenadas no formato esperado pelo Leaflet.
    const coordenadas = [
        LOCALIZACAO_ESTACAO.latitude,
        LOCALIZACAO_ESTACAO.longitude
    ];


    // Cria o mapa e define sua posição inicial.
    const mapa = L.map("mapa-estacao", {
        scrollWheelZoom: false
    }).setView(
        coordenadas,
        LOCALIZACAO_ESTACAO.zoom
    );


    // Adiciona os mapas do OpenStreetMap.
    //
    // Os mapas são carregados pela internet conforme
    // o usuário visualiza ou navega pela região.
    //
    // A atribuição aos colaboradores do OpenStreetMap
    // fica visível no canto inferior do mapa.

    L.tileLayer(
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,

            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }
    ).addTo(mapa);


    // Cria o marcador da estação meteorológica.
    const marcador = L.marker(coordenadas).addTo(mapa);


    // Configura a informação apresentada ao clicar no marcador.
    marcador.bindPopup(
        "<strong>Estação Meteorológica ESP32</strong><br>" +
        "Localização aproximada — São Paulo/SP"
    );


    // Apresenta uma mensagem abaixo do mapa.
    if (statusMapa) {

        statusMapa.textContent =
            "Marcador em localização aproximada na região central de São Paulo - SP.";
    }

    console.log("Mapa inicializado com sucesso.");
}


// ======================================================
// REGISTRO DE UMA NOVA MEDICAO NOS GRAFICOS
// ======================================================

function registrarMedicao(dados) {

    const horario = dados.ultima_atualizacao;

    // Sem horário, não é possível identificar uma nova medição.
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

        // Mantém os valores numéricos com duas casas decimais.
        valores[chave] = Number(Number(valor).toFixed(2));
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

    // Ao ultrapassar 60 amostras, remove a mais antiga.
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

        // Atualiza sem animações.
        grafico.update("none");
    });
}


// ======================================================
// FUNCAO AUXILIAR PARA ATUALIZAR OS CARTOES
// ======================================================

// Localiza um elemento HTML e atualiza seu conteúdo.
// Casas decimais opcionais para valores numéricos.

function atualizarElemento(id, valor, casasDecimais = null) {

    const elemento = document.getElementById(id);

    if (!elemento) {
        console.error("Elemento HTML não encontrado:", id);
        return;
    }

    // Apresenta "--" quando não há dados.
    if (valor === null || valor === undefined) {

        elemento.textContent = "--";
        return;
    }

    // Formata os valores numéricos.
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

        // Temperatura: duas casas decimais.
        atualizarElemento(
            "temperatura",
            dados.temperatura,
            2
        );

        // Umidade: duas casas decimais.
        atualizarElemento(
            "umidade",
            dados.umidade,
            2
        );

        // Pressão: duas casas decimais.
        atualizarElemento(
            "pressao",
            dados.pressao,
            2
        );

        // Luminosidade digital do LDR: mantém 0 ou 1.
        atualizarElemento(
            "luminosidade",
            dados.luminosidade
        );

        // ADC do MQ-135: duas casas decimais.
        atualizarElemento(
            "adc_mq135",
            dados.adc_mq135,
            2
        );

        // Classificação experimental da qualidade do ar.
        atualizarElemento(
            "qualidade_ar",
            dados.qualidade_ar
        );


        // --------------------------------------------------
        // 3. REGISTRO DA MEDICAO NOS GRAFICOS
        // --------------------------------------------------

        registrarMedicao(dados);


        // --------------------------------------------------
        // 4. ATUALIZACAO DO STATUS
        // --------------------------------------------------

        atualizarStatus(
            "ok",
            "Conectado à API"
        );


    } catch (erro) {

        atualizarStatus(
            "erro",
            "Falha ao carregar os dados. Tentando novamente..."
        );

        console.error("Erro ao consultar a API:", erro);

    } finally {

        // Libera a próxima consulta.
        consultaEmAndamento = false;
    }
}


// ======================================================
// INICIALIZACAO DO SISTEMA
// ======================================================

// Inicializa os quatro gráficos.
inicializarGraficos();

// Inicializa o mapa da estação.
inicializarMapa();

// Realiza a primeira consulta à API.
atualizarDados();

// Continua consultando a API a cada segundo.
setInterval(atualizarDados, 1000);
