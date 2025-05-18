import socket
import threading
import json
import time
import sys
import heapq
import subprocess

PORTA_BASE = 5000  # Cada roteador escuta em 5000 + ID

class Roteador:
    def __init__(self, id_roteador):
        self.id = id_roteador
        print(f"[{self.id}] Inicializando roteador...")

        self.porta = PORTA_BASE + id_roteador
        self.lsdb = {}  # Base de dados de estado de enlace

        self.vizinhos = self.carregar_vizinhos()
        print(f"[{self.id}] Vizinhos carregados: {self.vizinhos}")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.porta))
        print(f"[{self.id}] Socket UDP ligado na porta {self.porta}")

    def carregar_vizinhos(self):
        try:
            with open(f"topologia/roteador_{self.id}.json") as f:
                dados = json.load(f)
            return dados["vizinhos"]
        except Exception as e:
            print(f"[{self.id}] ⚠ Erro ao carregar vizinhos: {e}")
            return []

    def enviar_hello(self):
        while True:
            for vizinho in self.vizinhos:
                destino = (f"roteador{vizinho['id']}", PORTA_BASE + vizinho["id"])
                hello = {
                    "tipo": "HELLO",
                    "origem": self.id
                }
                try:
                    self.sock.sendto(json.dumps(hello).encode(), destino)
                    print(f"[{self.id}] Enviou HELLO para {vizinho['id']}")
                except Exception as e:
                    print(f"[{self.id}] ⚠ Erro ao enviar HELLO para {vizinho['id']}: {e}")
            time.sleep(5)

    def enviar_lsa(self):
        while True:
            lsa = {
                "tipo": "LSA",
                "origem": self.id,
                "vizinhos": self.vizinhos,
                "timestamp": time.time()
            }
            mensagem = json.dumps(lsa).encode()

            for vizinho in self.vizinhos:
                destino = (f"roteador{vizinho['id']}", PORTA_BASE + vizinho["id"])
                try:
                    self.sock.sendto(mensagem, destino)
                    print(f"[{self.id}] Enviou LSA para {vizinho['id']}")
                except Exception as e:
                    print(f"[{self.id}] ⚠ Falha ao enviar LSA para {vizinho['id']}: {e}")
            time.sleep(5)

    def receber(self):
        while True:
            try:
                dados, addr = self.sock.recvfrom(4096)
                print(f"[{self.id}] 🔍 Recebeu bruto: {dados}")

                pacote = json.loads(dados.decode())

                if pacote["tipo"] == "LSA":
                    origem = pacote["origem"]
                    if origem not in self.lsdb or self.lsdb[origem] != pacote["vizinhos"]:
                        self.lsdb[origem] = pacote["vizinhos"]
                        print(f"[{self.id}] Atualizou LSDB com LSA de {origem}: {pacote['vizinhos']}")
                        self.calcular_rotas()

                elif pacote["tipo"] == "HELLO":
                    origem = pacote["origem"]
                    print(f"[{self.id}] Recebeu HELLO de {origem}")
                    resposta = {
                        "tipo": "HELLO_ACK",
                        "origem": self.id
                    }
                    destino = (f"roteador{origem}", PORTA_BASE + origem)
                    self.sock.sendto(json.dumps(resposta).encode(), destino)

                elif pacote["tipo"] == "HELLO_ACK":
                    origem = pacote["origem"]
                    print(f"[{self.id}] Recebeu HELLO_ACK de {origem}")

            except Exception as e:
                print(f"[{self.id}] ⚠ Erro ao receber pacote: {e}")

    def iniciar(self):
        print(f"[{self.id}] Iniciando threads de envio e recepção...")
        threading.Thread(target=self.enviar_hello, daemon=True).start()
        threading.Thread(target=self.enviar_lsa, daemon=True).start()
        self.receber()

    def calcular_rotas(self):
        print(f"[{self.id}] 🧠 Calculando rotas com base na LSDB...")

        # Construir grafo a partir da LSDB
        grafo = {}
        for origem, vizinhos in self.lsdb.items():
            grafo[origem] = {}
            for v in vizinhos:
                grafo[origem][v["id"]] = v["custo"]

        # Incluir os próprios vizinhos
        grafo[self.id] = {}
        for v in self.vizinhos:
            grafo[self.id][v["id"]] = v["custo"]

        # Dijkstra
        dist = {n: float('inf') for n in grafo}
        anterior = {}
        dist[self.id] = 0
        fila = [(0, self.id)]

        while fila:
            custo, atual = heapq.heappop(fila)
            for vizinho in grafo.get(atual, {}):
                peso = grafo[atual][vizinho]
                if dist[vizinho] > dist[atual] + peso:
                    dist[vizinho] = dist[atual] + peso
                    anterior[vizinho] = atual
                    heapq.heappush(fila, (dist[vizinho], vizinho))

        # Construir tabela de rotas
        tabela = {}
        for destino in grafo:
            if destino == self.id:
                continue
            prox = destino
            while anterior.get(prox) != self.id:
                prox = anterior.get(prox)
                if prox is None:
                    break
            if prox is not None:
                tabela[destino] = prox

        print(f"[{self.id}] 📡 Tabela de roteamento:")
        for dest, prox in tabela.items():
            print(f"  Destino: {dest} → Próximo salto: {prox}")

        # Instalar rotas reais usando ip route
        for destino, prox in tabela.items():
            subrede_destino = f"10.0.{destino}.0/24"
            via_ip = f"10.0.{prox}.1"
            try:
                subprocess.run(
                    ["ip", "route", "replace", subrede_destino, "via", via_ip],
                    check=True
                )
                print(f"[{self.id}] ➕ Rota adicionada: {subrede_destino} via {via_ip}")
            except Exception as e:
                print(f"[{self.id}] ⚠ Erro ao adicionar rota: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 roteador.py <id>")
        sys.exit(1)

    id_roteador = int(sys.argv[1])
    roteador = Roteador(id_roteador)
    roteador.iniciar()
