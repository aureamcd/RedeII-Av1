import socket
import threading
import json
import time
import sys
import heapq
import os

PORTA_BASE = 5000

class Roteador:
    def __init__(self, id_roteador):
        self.id = id_roteador
        self.porta = PORTA_BASE + id_roteador
        self.lsdb = {self.id: self.carregar_vizinhos()}  # Inicializa LSDB com próprio LSA
        self.tabela_rotas = {}

        # Mapeamento consistente com docker-compose.yml
        self.id_para_ip = {
            0: "10.100.0.10",
            1: "10.100.0.11",
            2: "10.100.0.12",
            3: "10.100.0.13",
            4: "10.100.0.14"
        }

        print(f"[{self.id}] Inicializando roteador...")
        self.vizinhos = self.carregar_vizinhos()
        print(f"[{self.id}] Vizinhos carregados: {self.vizinhos}")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(5)  # Timeout para evitar bloqueio eterno
        try:
            self.sock.bind(("0.0.0.0", self.porta))
            print(f"[{self.id}] Socket ligado na porta {self.porta}")
        except OSError as e:
            print(f"[{self.id}] ⚠ Erro ao ligar socket: {e}")
            sys.exit(1)

    def carregar_vizinhos(self):
        try:
            with open(f"topologia/roteador_{self.id}.json") as f:
                dados = json.load(f)
            return dados["vizinhos"]
        except Exception as e:
            print(f"[{self.id}] ⚠ Erro ao carregar vizinhos: {e}")
            return []

    def enviar_lsa(self):
        # Espera inicial para garantir que todos estejam ouvindo
        time.sleep(2)
        
        while True:
            lsa = {
                "tipo": "LSA",
                "origem": self.id,
                "vizinhos": self.vizinhos,
                "timestamp": time.time()
            }
            mensagem = json.dumps(lsa).encode()
            
            for vizinho in self.vizinhos:
                destino = (self.id_para_ip[vizinho["id"]], PORTA_BASE + vizinho["id"])
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
                pacote = json.loads(dados.decode())

                if pacote["tipo"] == "LSA":
                    origem = pacote["origem"]
                    if origem not in self.lsdb or pacote["timestamp"] > self.lsdb.get(origem, {}).get("timestamp", 0):
                        self.lsdb[origem] = pacote
                        print(f"[{self.id}] Atualizou LSDB com LSA de {origem}")
                        self.calcular_rotas()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[{self.id}] ⚠ Erro ao receber pacote: {e}")

    def calcular_rotas(self):
        print(f"[{self.id}] 🧠 Calculando rotas com base na LSDB...")

        # Construir grafo completo
        grafo = {self.id: {v["id"]: v["custo"] for v in self.vizinhos}}
        for origem, dados in self.lsdb.items():
            if origem != self.id:
                grafo[origem] = {v["id"]: v["custo"] for v in dados["vizinhos"]}

        # Dijkstra
        dist = {n: float('inf') for n in grafo}
        anterior = {}
        dist[self.id] = 0
        fila = [(0, self.id)]

        while fila:
            custo, atual = heapq.heappop(fila)
            for vizinho, peso in grafo.get(atual, {}).items():
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
            while anterior.get(prox) != self.id and anterior.get(prox) is not None:
                prox = anterior.get(prox)
            if prox is not None:
                tabela[destino] = prox

        self.tabela_rotas = tabela
        self.instalar_rotas()

        print(f"[{self.id}] 📡 Tabela de roteamento atualizada:")
        for dest, prox in tabela.items():
            print(f"  Destino: {dest} → Próximo salto: {prox} (Custo: {dist[dest]})")

    def instalar_rotas(self):
        for destino, proximo_salto in self.tabela_rotas.items():
            via_ip = self.id_para_ip[proximo_salto]
            destino_rede = f"10.0.{destino}.0/24"

            # Remove rota existente se houver
            os.system(f"ip route del {destino_rede} 2>/dev/null")
            
            comando = f"ip route add {destino_rede} via {via_ip}"
            resultado = os.system(comando)
            if resultado == 0:
                print(f"[{self.id}] ➕ Rota adicionada: {destino_rede} via {via_ip}")
            else:
                print(f"[{self.id}] ⚠ Erro ao adicionar rota para {destino_rede}")

    def iniciar(self):
        print(f"[{self.id}] Iniciando threads...")
        threading.Thread(target=self.enviar_lsa, daemon=True).start()
        self.receber()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 roteador.py <id>")
        sys.exit(1)

    id_roteador = int(sys.argv[1])
    roteador = Roteador(id_roteador)
    roteador.iniciar()