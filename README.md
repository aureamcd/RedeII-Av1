# 🛰️ Projeto de Roteamento com Estado de Enlace (Link State) — Redes de Computadores II

## 👩‍💻 Autora
Áurea Letícia — Sistemas de Informação – UFPI  
Disciplina: Redes de Computadores II  
Professor: Dr. Rayner Gomes  
Data de entrega: 06/05/2025

---

## 🎯 Objetivo

Simular uma rede de computadores com múltiplas subredes, onde cada subrede possui dois hosts e um roteador. Os roteadores estão interconectados em uma topologia aleatória e trocam pacotes de controle usando o algoritmo de estado de enlace (Link State). A comunicação é realizada entre containers Docker utilizando Python.

---

## 🧱 Estrutura da Rede

- Cada subrede contém:
  - 2 hosts
  - 1 roteador
- Todos os elementos estão conectados por meio de redes bridge no Docker.
- Os roteadores se conectam entre si via uma rede comum chamada `roteador_net`.
- A topologia entre roteadores é aleatória e é gerada automaticamente pelo script `generate_topology.py`.

---

## ⚙️ Tecnologias Utilizadas

- 🐍 Python 3
- 🐳 Docker
- 🧱 Docker Compose
- 📡 Protocolo UDP

---

## 📦 Estrutura do Projeto

.
├── Dockerfile # Imagem base dos roteadores
├── Dockerfile.host # Imagem base dos hosts
├── docker-compose.yml # Define todos os containers e subredes
├── roteador.py # Código principal de cada roteador
├── generate_topology.py # Gera a topologia aleatória dos roteadores
└── README.md # Este documento


---

## 🚀 Como Executar o Projeto

1. Clone este repositório:
   ```bash
   git clone https://github.com/seuusuario/repo
   cd repo

2. Gere a topologia aleatória:
python3 generate_topology.py
Suba todos os containers:

bash
Copiar
Editar
docker-compose up --build
Acesse os containers para testes (exemplo):

bash
Copiar
Editar
docker exec -it host0a ping 10.0.4.10
📡 Justificativa do Protocolo (UDP)
Foi escolhido o protocolo UDP para a troca de pacotes de controle (Hello e LSA) entre os roteadores pelos seguintes motivos:

Baixa sobrecarga e maior velocidade

Tolerância a perdas de pacotes ocasionais

Ambiente controlado (Docker) com baixo risco de perda

Coerência com protocolos reais, como o OSPF, que também usam UDP

🌐 Como a Topologia é Gerada
A topologia é criada de forma aleatória pelo script generate_topology.py, que:

Gera conexões entre os roteadores de forma parcialmente conectada

Cria uma lista de vizinhos que cada roteador utilizará durante a execução

Simula os custos dos enlaces entre roteadores

📈 Limiares e Desempenho
O sistema foi testado com até 5 roteadores e 10 hosts. A troca de pacotes e o cálculo de rotas se mantiveram estáveis com baixa latência entre os nós. Gráficos de desempenho foram gerados no relatório anexo.

📊 Vantagens e Desvantagens da Abordagem
Vantagens:

Simplicidade na troca de pacotes

Baixo custo computacional

Modularidade (cada nó é isolado em um container)

Desvantagens:

Sem garantia de entrega dos pacotes UDP

Não há simulação real da tabela de roteamento do sistema operacional

❓ O host consegue 'pingar' qualquer outro?
Sim, após a convergência da LSDB e o cálculo das rotas com Dijkstra, qualquer host pode se comunicar com qualquer outro da rede usando ICMP (ping), pois o caminho é descoberto automaticamente pelos roteadores.

📹 Vídeo de Demonstração
👉 Assista aqui no YouTube

📄 Relatório
Diagrama de classes

Rede de Petri dos processos entre hosts e roteadores

Gráficos de desempenho

Explicações técnicas

O relatório completo está disponível em PDF na raiz do projeto.

✅ Critérios Atendidos
Critério	Status
Estrutura com Docker	✔️
Topologia aleatória	✔️
Threads/processos	✔️
Formato dos pacotes	✔️
Justificativa do protocolo	✔️
Armazenamento LSDB	✔️
Algoritmo de Dijkstra	✔️
Atualização da tabela de rotas	✔️
Documentação	✔️
Funcionamento e demonstração	✔️

📬 Contato
Caso tenha dúvidas ou sugestões, entre em contato comigo via [seuemail@ufpi.edu.br].







