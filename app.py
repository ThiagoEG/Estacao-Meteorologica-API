
from flask import Flask, jsonify, request, render_template


app = Flask(__name__)

@app.route("/dashboard")
def dashboard():
    return render_template("index.html")

dados = {
    "temperatura": None,
    "umidade": None,
    "pressao": None,
    "luminosidade": None,
    "gas": None
}

@app.route("/")
def inicio():
    return jsonify({"mensagem": "API da Estacao Meteorologica funcionando!"})

@app.route("/dados", methods=["GET", "POST"])
def gerenciar_dados():
    global dados

    if request.method == "POST":
        novos_dados = request.get_json(silent=True)

        if not isinstance(novos_dados, dict):
            return jsonify({"erro": "Envie um objeto JSON"}), 400

        campos = dados.keys()

        if not all(campo in novos_dados for campo in campos):
            return jsonify({"erro": "Faltam campos dos sensores"}), 400

        dados = {campo: novos_dados[campo] for campo in campos}
        return jsonify({"mensagem": "Dados recebidos", "dados": dados}), 200

    return jsonify(dados)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
