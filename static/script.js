
// ======================================================
// FUNÇÃO RESPONSÁVEL POR ATUALIZAR OS DADOS DA DASHBOARD
// ======================================================

// "async" permite utilizar "await" dentro da função.
// Isso possibilita aguardar respostas de operações que
// demoram algum tempo, como uma consulta à API.
async function atualizarDados() {

    // Localiza no HTML o elemento que apresenta mensagens
    // de status para o usuário.
    const status = document.getElementById("status");

    try {

        // ==================================================
        // 1. CONSULTA À API
        // ==================================================

        // Realiza uma requisição HTTP para o endereço "/dados".
        // Esse endereço é disponibilizado pela API e retorna
        // as informações mais recentes dos sensores.
        const resposta = await fetch("/dados", {

            // Impede que o navegador utilize uma resposta
            // antiga armazenada em cache.
            // Assim, buscamos os dados atualizados da API.
            cache: "no-store"
        });

        // Verifica se a requisição foi respondida corretamente.
        // Caso ocorra um erro HTTP, interrompe a execução
        // e direciona o programa para o bloco "catch".
        if (!resposta.ok) {
            throw new Error("Erro HTTP: " + resposta.status);
        }

        // Converte a resposta recebida da API para um objeto
        // JavaScript, permitindo acessar cada informação
        // individualmente.
        const dados = await resposta.json();


        // ==================================================
        // 2. ATUALIZAÇÃO DAS INFORMAÇÕES NA DASHBOARD
        // ==================================================

        // TEMPERATURA:
        // Obtém o valor enviado pela API e apresenta no
        // elemento HTML identificado como "temperatura".
        // O operador "??" utiliza "--" caso o valor seja
        // nulo ou não esteja definido.
        document.getElementById("temperatura").textContent =
            dados.temperatura ?? "--";


        // UMIDADE:
        // Apresenta a umidade relativa do ar recebida da API.
        document.getElementById("umidade").textContent =
            dados.umidade ?? "--";


        // PRESSÃO ATMOSFÉRICA:
        // Apresenta a pressão recebida da API em hPa.
        // "toFixed(2)" mantém duas casas decimais.
        // Caso não exista um valor, apresenta "--".
        //
        // A conversão para hPa já é realizada na ESP32.
        // A unidade hPa já está definida no HTML, portanto
        // aqui apresentamos somente o valor numérico.
        document.getElementById("pressao").textContent =
            dados.pressao == null
                ? "--"
                : Number(dados.pressao).toFixed(2);


        // LUMINOSIDADE:
        // Apresenta o valor recebido do sensor LDR.
        // Neste projeto, a leitura utiliza a saída digital (DO),
        // que retorna os estados 0 ou 1.
        document.getElementById("luminosidade").textContent =
            dados.luminosidade ?? "--";


        // ==================================================
        // 3. ATUALIZAÇÃO DAS INFORMAÇÕES DO MQ-135
        // ==================================================

        // VALOR ADC:
        // Apresenta a média das leituras analógicas realizadas
        // pelo sensor MQ-135.
        //
        // "Number()" garante que o valor seja tratado como número.
        // "toFixed(1)" apresenta uma casa decimal.
        //
        // Esse valor representa a leitura do ADC, não uma
        // concentração de gás em PPM.
        document.getElementById("adc_mq135").textContent =
            dados.adc_mq135 == null
                ? "--"
                : Number(dados.adc_mq135).toFixed(1);


        // QUALIDADE DO AR:
        // Apresenta a classificação enviada pela ESP32,
        // calculada com base na média das leituras do MQ-135.
        //
        // As classificações utilizadas são:
        // EXCELENTE, BOA, MODERADA, RUIM e PESSIMA.
        document.getElementById("qualidade_ar").textContent =
            dados.qualidade_ar ?? "--";


        // ==================================================
        // 4. ATUALIZAÇÃO DO STATUS
        // ==================================================

        // Limpa a mensagem inicial de carregamento ou qualquer
        // mensagem de erro anterior quando a consulta funciona.
        status.textContent = "";


    } catch (erro) {

        // ==================================================
        // 5. TRATAMENTO DE ERROS
        // ==================================================

        // Caso aconteça algum problema durante a consulta
        // ou o processamento dos dados, apresenta uma
        // mensagem para informar o usuário.
        status.textContent =
            "Falha ao carregar os dados. Tentando novamente...";

        // Registra os detalhes do erro no console do navegador.
        // Isso facilita a identificação de problemas durante
        // os testes e a manutenção do sistema.
        console.error("Erro ao consultar a API:", erro);
    }
}


// ======================================================
// 6. INICIALIZAÇÃO E ATUALIZAÇÃO AUTOMÁTICA
// ======================================================

// Executa a função imediatamente quando o JavaScript
// é carregado, sem precisar esperar o primeiro intervalo.
atualizarDados();

// Executa novamente a função a cada 1.000 milissegundos,
// ou seja, a cada 1 segundo.
//
// Dessa forma, a dashboard consulta continuamente a API
// para apresentar os dados mais recentes dos sensores.
setInterval(atualizarDados, 1000);
