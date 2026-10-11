
async function atualizarDados() {
    const status = document.getElementById("status");

    try {
        const resposta = await fetch("/dados");

        if (!resposta.ok) {
            throw new Error("Erro HTTP: " + resposta.status);
        }

        const dados = await resposta.json();

        document.getElementById("temperatura").textContent =
            dados.temperatura ?? "--";

        document.getElementById("umidade").textContent =
            dados.umidade ?? "--";

        document.getElementById("pressao").textContent =
            dados.pressao == null
                ? "--"
                : (dados.pressao / 100).toFixed(2);

        document.getElementById("luminosidade").textContent =
            dados.luminosidade ?? "--";

        document.getElementById("gas").textContent =
            dados.gas ?? "--";

        status.textContent =
            "Última atualização: " +
            new Date().toLocaleTimeString("pt-BR");

    } catch (erro) {
        status.textContent =
            "Falha ao carregar os dados. Tentando novamente...";

        console.error("Erro ao consultar a API:", erro);
    }
}

atualizarDados();
setInterval(atualizarDados, 5000);
