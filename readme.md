# Estação Meteorológica com ESP32

Projeto de uma estação meteorológica para monitoramento de condições ambientais. A estação utiliza uma **ESP32** e sensores para coletar informações do ambiente, envia as leituras para uma **API desenvolvida em Flask** e disponibiliza os dados em uma **dashboard web**.

O projeto foi desenvolvido com foco em Internet das Coisas (IoT) e monitoramento ambiental, podendo servir como base para a divulgação pública de dados coletados por uma estação física.

## Visão geral

O funcionamento do sistema é dividido em três partes:

1. **ESP32:** realiza a leitura dos sensores e organiza os resultados em um objeto JSON.
2. **API Flask:** recebe os dados enviados pela ESP32 e disponibiliza a leitura mais recente por meio de uma rota HTTP.
3. **Dashboard:** consulta a API e apresenta os valores em uma página web.

### Arquitetura

Sensores 
       │
       ▼
 ESP32 (MicroPython)
       │
       │ HTTP POST /dados
       ▼
 API Flask (Render)
       │
       │ HTTP GET /dados
       ▼
 Dashboard web

## Tecnologias utilizadas

- **MicroPython:** programação da ESP32.
- **ESP32:** unidade responsável pela leitura dos sensores e comunicação Wi-Fi.
- **Flask:** desenvolvimento da API em Python.
- **HTML, CSS e JavaScript:** construção e atualização da dashboard.
- **Render:** hospedagem da API e da aplicação web.
- **Git e GitHub:** versionamento e disponibilização do código-fonte.

## Sensores utilizados

| Sensor | Informação coletada | Interface / pino na ESP32 |
|---|---|---|
| DHT22 | Temperatura e umidade relativa do ar | GPIO 4 |
| BMP280 | Pressão atmosférica | I²C: SDA GPIO 21 e SCL GPIO 22 |
| LDR (módulo com saída DO) | Estado digital relacionado à luminosidade | GPIO 34 |
| MQ-135 | Resposta analógica do sensor utilizada como indicador experimental da qualidade do ar | GPIO 35 (ADC) |

### Observações sobre as leituras

- **DHT22:** fornece temperatura em graus Celsius e umidade relativa em porcentagem.
- **BMP280:** a pressão é convertida de Pascal (Pa) para hectopascal (hPa) antes de ser enviada à API. O endereço I²C utilizado no código é `0x76`.
- **LDR:** o projeto utiliza a saída digital (DO) do módulo. Portanto, a leitura é um estado lógico (0 ou 1), e não uma medição de luminosidade em lux. O potenciômetro do módulo influencia o ponto de acionamento.
- **MQ-135:** a saída analógica é lida pelo ADC da ESP32. O código calcula a média de várias amostras para reduzir pequenas oscilações. O valor é enviado no campo `gas`.

A classificação experimental do MQ-135 utilizada no firmware é:

| Média ADC | Classificação apresentada no monitor serial |
|---:|---|
| Até 410 | EXCELENTE |
| Acima de 410 até 450 | BOA |
| Acima de 450 até 550 | MODERADA |
| Acima de 550 até 700 | RUIM |
| Acima de 700 | PESSIMA |

Essas faixas foram definidas a partir dos testes realizados com o módulo utilizado no projeto. **Não são um índice oficial de qualidade do ar, não identificam quais gases estão presentes e não devem ser utilizadas como comprovação de que o ar está seguro.**

## Estrutura do repositório

Estrutura do repositório:

Estacao-Meteorologica-API/
├── app.py                       # API Flask e rotas da aplicação
├── requirements.txt             # Dependências Python da API
├── render.yaml                  # Configuração de implantação no Render
├── templates/
│   └── index.html               # Página principal da dashboard
├── static/
│   ├── css/                     # Folhas de estilo da dashboard
│   └── js/                      # JavaScript da dashboard
└── esp32/
    ├── main.py                  # Programa principal da ESP32
    └── bmp280.py                # Driver MicroPython do sensor BMP280

A estrutura pode variar conforme a organização atual dos arquivos no repositório.

## Configuração da ESP32

O firmware está na pasta `esp32/` e utiliza MicroPython.

### 1. Preparar as credenciais Wi-Fi

No arquivo `main.py`, configure o nome e a senha da rede Wi-Fi:


WIFI_SSID = "NOME_DA_REDE"
WIFI_PASSWORD = "SENHA_DA_REDE"


Use valores fictícios nos exemplos publicados no GitHub. Não publique senhas reais. Para uso local, configure as credenciais da sua própria rede antes de executar o programa.

### 2. Conferir o endereço da API

O firmware envia os dados para o endpoint:

API_URL = "https://estacao-meteorologica-api.onrender.com/dados"


Caso a aplicação seja hospedada em outro endereço, atualize essa configuração no `main.py`.

### 3. Arquivos necessários na ESP32

Transfira para a ESP32 os arquivos necessários ao firmware, incluindo:

- `main.py`;
- `bmp280.py`;
- a biblioteca `dht` disponibilizada pelo firmware MicroPython;
- a biblioteca `urequests`, caso ela não esteja incluída no firmware utilizado.

O arquivo `bmp280.py` deve estar disponível no dispositivo para que a importação `from bmp280 import BMP280` funcione.

### 4. Executar

Após configurar o Wi-Fi e transferir os arquivos, inicie a ESP32. O programa tenta conectar-se à rede, realiza as leituras dos sensores e envia os dados para a API.

## API

A API foi desenvolvida com Flask e está hospedada no Render.

**Endereço-base:** https://estacao-meteorologica-api.onrender.com/

### Rotas disponíveis

| Método | Rota | Função |
|---|---|---|
| GET | `/` | Retorna uma mensagem indicando que a API está disponível. |
| GET | `/dados` | Retorna os dados mais recentes recebidos dos sensores. |
| POST | `/dados` | Recebe e atualiza os dados enviados pela ESP32. |
| GET | `/dashboard` | Exibe a página da dashboard. |

### Formato dos dados

Atualmente, a API espera um objeto JSON com os cinco campos abaixo:

{
  "temperatura": 26.0,
  "umidade": 77.0,
  "pressao": 934.22,
  "luminosidade": 1,
  "adc_mq135": adc_mq135,
  "qualidade_ar": qualidade_ar
}

### Testar a API

Para consultar os dados mais recentes, acesse:

- [API — página inicial](https://estacao-meteorologica-api.onrender.com/)
- [API — dados dos sensores](https://estacao-meteorologica-api.onrender.com/dados)
- [Dashboard](https://estacao-meteorologica-api.onrender.com/dashboard)

A rota `GET /dados` retorna os valores armazenados mais recentemente pela aplicação.

## Dashboard

A dashboard consulta a rota `GET /dados` e atualiza os elementos da página com os valores retornados pela API. O JavaScript utiliza uma atualização automática configurada para ocorrer a cada 1 segundo.

A frequência de consulta da dashboard é independente da frequência de leitura e envio da ESP32. A página pode consultar a API mais vezes do que a ESP32 envia novas medições; nesse caso, algumas consultas apresentarão os mesmos valores até a chegada de uma nova leitura.

## Como executar a API localmente

É necessário ter Python instalado.

1. Clone o repositório:


   git clone https://github.com/ThiagoEG/Estacao-Meteorologica-API.git


2. Entre na pasta do projeto:


   cd Estacao-Meteorologica-API


3. Crie e ative um ambiente virtual, se desejar:

   python -m venv venv

   No Windows (PowerShell):

   .\venv\Scripts\Activate.ps1

4. Instale as dependências:

   pip install -r requirements.txt

5. Inicie a aplicação:

   python app.py

## Limitações atuais

- Os dados são mantidos em memória pela aplicação Flask. Não há banco de dados nesta versão; após uma reinicialização do processo, os valores podem voltar a ficam congelados até a ESP32 enviar novas leituras.
- A leitura digital do LDR não fornece valores em lux.
- A disponibilidade da aplicação depende do serviço de hospedagem e da conexão de rede da ESP32.

## Possíveis melhorias futuras

- Disponibilizar gráficos de evolução das variáveis ambientais.
- Utilizar uma leitura analógica do sensor de luminosidade para obter medidas mais detalhadas, com calibração apropriada.
