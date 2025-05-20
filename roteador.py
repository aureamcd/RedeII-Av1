import subprocess
import socket
import threading
import json
import time
import sys
import heapq

PORTA_BASE = 5000
MAX_PACOTE_ANTIGO = 10
ACK_TIMEOUT = 2
MAX_RETRANSMISSOES = 3
INTERVALO_LSA_INICIAL = 5

def ativar_ip_forward():
    resultado = subprocess.run(
        "sysctl -w net.ipv4.ip_forward=1", shell=True, capture_output=True)
    print("✅ IP forwarding ativado" if resultado.returncode ==
          0 else f"❌ Falha ao ativar: {resultado.stderr.decode()}")

class Roteador:
    def __init__(self, id_roteador):
        self.id = id_roteador
        self.porta = PORTA_BASE + id_roteador
        self.vizinhos = self.carregar_vizinhos()
        self.sequence_id = 0
        self.received_sequences = {}
        self.lsdb = {
            self.id: {
                "tipo": "LSA",
                "origem": self.id,
                "vizinhos": self.vizinhos,
                "sequence_id": self.sequence_id,
                "timestamp": time.time()
            }
        }

        self.tabela_rotas = {}
        self.rotas_instaladas = set()
        self.lock = threading.Lock()

        self.id_para_ip = {
            0: "10.100.0.10",
            1: "10.100.0.11",
            2: "10.100.0.12",
            3: "10.100.0.13",
            4: "10.100.0.14"
        }

        self.acks_recebidos = {v["id"]: threading.Event() for v in self.vizinhos}
        self.perdas_vizinho = {v["id"]: 0 for v in self.vizinhos}

        self.intervalo_lsa = INTERVALO_LSA_INICIAL

        print(f"[{self.id}] Inicializando com vizinhos: {self.vizinhos}")

        self.sock = self.inicializar_socket()
        self.sock_broadcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_broadcast.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def inicializar_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(5)
        try:
            sock.bind(("0.0.0.0", self.porta))
            print(f"[{self.id}] Socket ligado na porta {self.porta}")
        except OSError as e:
            print(f"[{self.id}] ⚠ Erro ao ligar socket: {e}")
            sys.exit(1)
        return sock

    def carregar_vizinhos(self):
        try:
            with open(f"topologia/roteador_{self.id}.json") as f:
                return json.load(f)["vizinhos"]
        except Exception as e:
            print(f"[{self.id}] ⚠ Erro ao carregar vizinhos: {e}")
            return []

    def enviar_lsa(self):
        time.sleep(2)
        while True:
            with self.lock:
                self.sequence_id += 1
                lsa = {
                    "tipo": "LSA",
                    "origem": self.id,
                    "vizinhos": self.vizinhos,
                    "sequence_id": self.sequence_id,
                    "timestamp": time.time()
                }

            for vizinho in self.vizinhos:
                sucesso = False
                tentativas = 0
                self.acks_recebidos.setdefault(vizinho["id"], threading.Event()).clear()
                while not sucesso and tentativas < MAX_RETRANSMISSOES:
                    self.enviar_pacote(lsa, vizinho)
                    if self.acks_recebidos[vizinho["id"]].wait(ACK_TIMEOUT):
                        sucesso = True
                        self.perdas_vizinho[vizinho["id"]] = 0
                    else:
                        tentativas += 1
                        self.perdas_vizinho[vizinho["id"]] += 1
                        print(f"[{self.id}] ⚠ Retransmitindo LSA para {vizinho['id']} (tentativa {tentativas})")
                if not sucesso:
                    print(f"[{self.id}] ❌ Falha ao receber ACK de {vizinho['id']} após {MAX_RETRANSMISSOES} tentativas")

            perdas_totais = sum(self.perdas_vizinho.values())
            if perdas_totais > len(self.vizinhos) * 1:
                self.intervalo_lsa = min(self.intervalo_lsa * 1.5, 30)
                print(f"[{self.id}] ⚠ Alta perda detectada. Aumentando intervalo LSA para {self.intervalo_lsa:.1f}s")
            else:
                self.intervalo_lsa = max(self.intervalo_lsa * 0.9, INTERVALO_LSA_INICIAL)

            time.sleep(self.intervalo_lsa)

    def enviar_pacote(self, pacote, vizinho):
        destino = (self.id_para_ip[vizinho["id"]], PORTA_BASE + vizinho["id"])
        try:
            self.sock.sendto(json.dumps(pacote).encode(), destino)
            print(f"[{self.id}] Enviou {pacote['tipo']} (seq={pacote.get('sequence_id', '-')}) → {vizinho['id']}")
        except Exception as e:
            print(f"[{self.id}] ⚠ Erro ao enviar pacote para {vizinho['id']}: {e}")

    def repassar_lsa(self, pacote):
        if pacote["origem"] == self.id:
            return
        if time.time() - pacote.get("timestamp", 0) > MAX_PACOTE_ANTIGO:
            print(f"[{self.id}] ⚠ Ignorando LSA antigo (timestamp expirado)")
            return

        for vizinho in self.vizinhos:
            if vizinho["id"] != pacote.get("ultimo_salto"):
                pacote["ultimo_salto"] = self.id
                self.enviar_pacote(pacote, vizinho)

    def enviar_hello(self):
        while True:
            msg = json.dumps({"tipo": "HELLO", "origem": self.id}).encode()
            try:
                self.sock_broadcast.sendto(msg, ("10.100.0.255", PORTA_BASE))
                print(f"[{self.id}] HELLO broadcast")
            except Exception as e:
                print(f"[{self.id}] ⚠ Falha HELLO: {e}")
            time.sleep(5)

    def receber(self):
        while True:
            try:
                dados, _ = self.sock.recvfrom(4096)
                self.processar_pacote(json.loads(dados.decode()))
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[{self.id}] ⚠ Pacote inválido: {e}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[{self.id}] ⚠ Erro inesperado: {e}")

    def processar_pacote(self, pacote):
        if pacote["tipo"] == "LSA":
            origem = pacote["origem"]
            seq = pacote["sequence_id"]

            # Garante estruturas para novos vizinhos
            if origem not in self.acks_recebidos:
                self.acks_recebidos[origem] = threading.Event()
            if origem not in self.perdas_vizinho:
                self.perdas_vizinho[origem] = 0

            ack = {
                "tipo": "ACK",
                "origem": self.id,
                "seq_ack": seq,
                "destino": origem
            }
            destino_ip = self.id_para_ip[origem]
            destino_porta = PORTA_BASE + origem
            try:
                self.sock.sendto(json.dumps(ack).encode(), (destino_ip, destino_porta))
                print(f"[{self.id}] Enviou ACK para {origem} (seq={seq})")
            except Exception as e:
                print(f"[{self.id}] ⚠ Falha ao enviar ACK: {e}")

            if time.time() - pacote.get("timestamp", 0) > MAX_PACOTE_ANTIGO:
                print(f"[{self.id}] ⚠ Ignorando LSA antigo (timestamp expirado)")
                return

            if seq > self.received_sequences.get(origem, -1):
                with self.lock:
                    self.received_sequences[origem] = seq
                    self.lsdb[origem] = pacote
                    print(f"[{self.id}] ✅ LSA novo de {origem} (seq={seq})")
                    self.calcular_rotas()
                    self.repassar_lsa(pacote)
            else:
                print(f"[{self.id}] ⚠ LSA antigo de {origem} (seq={seq})")

        elif pacote["tipo"] == "HELLO":
            print(f"[{self.id}] Recebeu HELLO de {pacote['origem']}")

        elif pacote["tipo"] == "ACK":
            origem = pacote["origem"]
            if origem in self.acks_recebidos:
                self.acks_recebidos[origem].set()
                print(f"[{self.id}] ACK recebido de {origem} (seq={pacote['seq_ack']})")

    def calcular_rotas(self):
        print(f"[{self.id}] 🔍 Iniciando cálculo de rotas...")
        grafo = {origem: {v["id"]: v["custo"] for v in dados["vizinhos"]} for origem, dados in self.lsdb.items()}
        print(f"[{self.id}] 🌐 Grafo atual: {grafo}")

        todos_nos = set(grafo.keys())
        for vizinhos in grafo.values():
            todos_nos.update(vizinhos.keys())

        dist = {n: float("inf") for n in todos_nos}
        dist[self.id] = 0
        anterior = {}

        fila = [(0, self.id)]

        while fila:
            custo, atual = heapq.heappop(fila)
            for vizinho, peso in grafo.get(atual, {}).items():
                if dist[vizinho] > custo + peso:
                    dist[vizinho] = custo + peso
                    anterior[vizinho] = atual
                    heapq.heappush(fila, (dist[vizinho], vizinho))

        print(f"[{self.id}] 🗺️ Tabela de distâncias (Dijkstra): {dist}")

        tabela = {}
        for destino in grafo:
            if destino == self.id:
                continue
            prox = destino
            while anterior.get(prox) != self.id and prox in anterior:
                prox = anterior[prox]
            if prox in anterior or anterior.get(prox) == self.id:
                tabela[destino] = prox

        with self.lock:
            if tabela != self.tabela_rotas:
                print(f"[{self.id}] 📡 Tabela de roteamento atualizada: {tabela}")
                self.tabela_rotas = tabela
                self.instalar_rotas()
            else:
                print(f"[{self.id}] 💤 Nenhuma mudança na tabela de roteamento.")

        for dest, prox in tabela.items():
            print(f"  Destino: {dest} → Próximo: {prox} (Custo: {dist[dest]})")

    def instalar_rotas(self):
        print(f"[{self.id}] 🚧 Instalando rotas...")

        destinos_atuais = {f"10.0.{dest}.0/24" for dest in self.tabela_rotas.keys()}
        rotas_para_remover = self.rotas_instaladas - destinos_atuais
        for rota in rotas_para_remover:
            print(f"[{self.id}] ❌ Removendo rota obsoleta: {rota}")
            subprocess.run(f"ip route del {rota}", shell=True, stderr=subprocess.DEVNULL)

        for destino, proximo in self.tabela_rotas.items():
            via_ip = self.id_para_ip[proximo]
            destino_rede = f"10.0.{destino}.0/24"
            cmd_show = subprocess.run(f"ip route show {destino_rede}", shell=True, capture_output=True, text=True)
            rota_existente = cmd_show.stdout.strip()

            if rota_existente and via_ip not in rota_existente:
                subprocess.run(f"ip route del {destino_rede}", shell=True, stderr=subprocess.DEVNULL)
                rota_existente = ""

            if not rota_existente:
                cmd_add = f"ip route add {destino_rede} via {via_ip}"
                resultado = subprocess.run(cmd_add, shell=True, capture_output=True)
                if resultado.returncode == 0:
                    print(f"[{self.id}] ✅ Rota adicionada com sucesso: {destino_rede} via {via_ip}")
                else:
                    print(f"[{self.id}] ❌ Falha ao adicionar rota: {resultado.stderr.decode()}")

        self.rotas_instaladas = destinos_atuais
        print(f"[{self.id}] 📦 Rotas instaladas agora: {self.rotas_instaladas}")

    def iniciar(self):
        print(f"[{self.id}] Iniciando roteador...")
        threading.Thread(target=self.enviar_lsa, daemon=True).start()
        threading.Thread(target=self.enviar_hello, daemon=True).start()
        self.receber()

if __name__ == "__main__":
    ativar_ip_forward()
    if len(sys.argv) != 2:
        print("Uso: python3 roteador.py <id>")
        sys.exit(1)

    roteador = Roteador(int(sys.argv[1]))
    roteador.iniciar()
