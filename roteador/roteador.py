import subprocess
import socket
import threading
import json
import time
import sys
import heapq
import os

PORTA_BASE = 5000
MAX_PACOTE_ANTIGO = 10
INTERVALO_LSA_INICIAL = 5


def ativar_ip_forward():
    resultado = subprocess.run(
        "sysctl -w net.ipv4.ip_forward=1", shell=True, capture_output=True)
    print("✅ IP forwarding ativado" if resultado.returncode ==
          0 else f"❌ Falha ao ativar: {resultado.stderr.decode()}")


class Roteador:
    def __init__(self, nome_roteador):
        self.nome = nome_roteador
        # Mapeamento de nomes para IDs baseado no compose file - movido para antes de obter_id_do_nome
        self.nome_para_id = {
            "r1": 1,
            "r2": 2,
            "r3": 3,
            "r4": 4,
            "r5": 5
        }
        
        # Criando mapeamento reverso - movido para antes de obter_id_do_nome
        self.id_para_nome = {v: k for k, v in self.nome_para_id.items()}
        
        self.id = self.obter_id_do_nome()
        self.porta = PORTA_BASE
        
        # Mapeamento de IDs para IPs baseado no compose file - movido para antes de descobrir_vizinhos
        self.id_para_ip = self.criar_mapeamento_ips()
        
        self.vizinhos = self.descobrir_vizinhos()
        print(f"[{self.nome}] Vizinhos carregados: {self.vizinhos}")
        
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
        
        self.intervalo_lsa = INTERVALO_LSA_INICIAL

        print(f"[{self.nome}] Inicializando com ID {self.id} e vizinhos: {self.vizinhos}")

        self.sock = self.inicializar_socket()
        self.sock_broadcast = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_broadcast.setsockopt(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def obter_id_do_nome(self):
        """Obtém o ID do roteador baseado no nome do container"""
        container_name = os.environ.get('CONTAINER_NAME', '')
        if not container_name:
            print(f"⚠ Variável de ambiente CONTAINER_NAME não definida, usando hostname")
            container_name = socket.gethostname()
        
        if container_name in self.nome_para_id:
            return self.nome_para_id[container_name]
        else:
            print(f"⚠ Nome de container não reconhecido: {container_name}")
            return 0

    def criar_mapeamento_ips(self):
        """Cria mapeamento de IDs para IPs baseado na topologia do docker-compose"""
        mapeamento = {}
        
        # Mapeamento baseado nas conexões entre roteadores
        # Para cada roteador, usamos seu IP na rede conectada ao destino
        
        # Para r1 (ID 1)
        mapeamento[1] = {
            2: "10.10.1.3",  # r1 para r2 - corrigido
            3: "10.10.2.3",  # r1 para r3 - corrigido
        }
        
        # Para r2 (ID 2)
        mapeamento[2] = {
            1: "10.10.1.2",  # r2 para r1 - corrigido
            4: "10.10.3.3",  # r2 para r4 - corrigido
        }
        
        # Para r3 (ID 3)
        mapeamento[3] = {
            1: "10.10.2.2",  # r3 para r1 - corrigido
            4: "10.10.4.3",  # r3 para r4 - corrigido
        }
        
        # Para r4 (ID 4)
        mapeamento[4] = {
            2: "10.10.3.2",  # r4 para r2 - corrigido
            3: "10.10.4.2",  # r4 para r3 - corrigido
            5: "10.10.5.3",  # r4 para r5 - corrigido
        }
        
        # Para r5 (ID 5)
        mapeamento[5] = {
            4: "10.10.5.2",  # r5 para r4 - corrigido
        }
        
        return mapeamento

    def inicializar_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(5)
        try:
            sock.bind(("0.0.0.0", self.porta))
            print(f"[{self.nome}] Socket ligado na porta {self.porta}")
        except OSError as e:
            print(f"[{self.nome}] ⚠ Erro ao ligar socket: {e}")
            sys.exit(1)
        return sock

    def descobrir_vizinhos(self):
        """Descobre vizinhos baseado na configuração de rede do docker-compose"""
        vizinhos = []
        
        # Mapeamento baseado no docker-compose
        topologia = {
            1: [  # r1
                {"id": 2, "custo": 1},  # r2
                {"id": 3, "custo": 1},  # r3
            ],
            2: [  # r2
                {"id": 1, "custo": 1},  # r1
                {"id": 4, "custo": 1},  # r4
            ],
            3: [  # r3
                {"id": 1, "custo": 1},  # r1
                {"id": 4, "custo": 1},  # r4
            ],
            4: [  # r4
                {"id": 2, "custo": 1},  # r2
                {"id": 3, "custo": 1},  # r3
                {"id": 5, "custo": 1},  # r5
            ],
            5: [  # r5
                {"id": 4, "custo": 1},  # r4
            ],
        }
        
        if self.id in topologia:
            vizinhos = topologia[self.id]
            print(f"[{self.nome}] Vizinhos descobertos: {vizinhos}")
        else:
            print(f"[{self.nome}] ⚠ ID {self.id} não encontrado na topologia!")
        
        return vizinhos

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
                self.lsdb[self.id] = lsa

            for vizinho in self.vizinhos:
                print(
                    f"[{self.nome}] Enviando LSA para {vizinho['id']} ({self.id_para_nome.get(vizinho['id'], 'desconhecido')})")
                self.enviar_pacote(lsa, vizinho)

            time.sleep(self.intervalo_lsa)

    def enviar_pacote(self, pacote, vizinho):
        destino_id = vizinho["id"]
        
        # Obtém o IP do roteador vizinho para comunicação
        if self.id in self.id_para_ip and destino_id in self.id_para_ip[self.id]:
            destino_ip = self.id_para_ip[self.id][destino_id]
        else:
            print(f"[{self.nome}] ⚠ Não foi possível determinar IP para o vizinho {destino_id}")
            return
            
        destino = (destino_ip, PORTA_BASE)
        print(f"[{self.nome}] Enviando pacote para {destino}")
        try:
            self.sock.sendto(json.dumps(pacote).encode(), destino)
            print(
                f"[{self.nome}] Enviou {pacote['tipo']} (seq={pacote.get('sequence_id', '-')}) → {destino_id} ({self.id_para_nome.get(destino_id, 'desconhecido')})")
        except Exception as e:
            print(f"[{self.nome}] ⚠ Erro ao enviar pacote para {destino_id}: {e}")

    def repassar_lsa(self, pacote):
        if pacote["origem"] == self.id:
            return
        if time.time() - pacote.get("timestamp", 0) > MAX_PACOTE_ANTIGO:
            print(f"[{self.nome}] ⚠ Ignorando LSA antigo (timestamp expirado)")
            return

        # Registra quem enviou este pacote como último salto
        ultimo_salto = pacote.get("ultimo_salto")
        
        for vizinho in self.vizinhos:
            # Não repassa para quem enviou o LSA
            if vizinho["id"] != ultimo_salto:
                pacote_repasse = dict(pacote)
                pacote_repasse["ultimo_salto"] = self.id
                self.enviar_pacote(pacote_repasse, vizinho)

    def enviar_hello(self):
        while True:
            # Para cada vizinho, enviamos um HELLO específico
            for vizinho in self.vizinhos:
                msg = json.dumps({"tipo": "HELLO", "origem": self.id}).encode()
                try:
                    if self.id in self.id_para_ip and vizinho["id"] in self.id_para_ip[self.id]:
                        destino_ip = self.id_para_ip[self.id][vizinho["id"]]
                        self.sock.sendto(msg, (destino_ip, PORTA_BASE))
                        print(f"[{self.nome}] HELLO para {vizinho['id']} ({self.id_para_nome.get(vizinho['id'], 'desconhecido')})")
                    else:
                        print(f"[{self.nome}] ⚠ Não foi possível encontrar IP para vizinho {vizinho['id']}")
                except Exception as e:
                    print(f"[{self.nome}] ⚠ Falha HELLO para {vizinho['id']}: {e}")
            time.sleep(5)

    def receber(self):
        while True:
            try:
                dados, endereco = self.sock.recvfrom(4096)
                print(f"[{self.nome}] Recebeu dados de {endereco}")
                self.processar_pacote(json.loads(dados.decode()), endereco)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[{self.nome}] ⚠ Pacote inválido: {e}")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[{self.nome}] ⚠ Erro inesperado: {e}")

    def processar_pacote(self, pacote, endereco):
        print(f"[{self.nome}] Recebeu pacote: {pacote} de {endereco}")
        if pacote["tipo"] == "LSA":
            origem = pacote["origem"]
            print(f"[{self.nome}] Recebeu LSA de {origem} ({self.id_para_nome.get(origem, 'desconhecido')})")
            seq = pacote["sequence_id"]

            if time.time() - pacote.get("timestamp", 0) > MAX_PACOTE_ANTIGO:
                print(f"[{self.nome}] ⚠ Ignorando LSA antigo (timestamp expirado)")
                return

            # Se já tivermos um LSA mais recente deste roteador, ignoramos
            if origem in self.received_sequences and seq <= self.received_sequences[origem]:
                print(f"[{self.nome}] ⚠ LSA antigo ou duplicado de {origem} (seq={seq})")
                return
            
            with self.lock:
                self.received_sequences[origem] = seq
                self.lsdb[origem] = pacote
                print(f"[{self.nome}] ✅ LSA novo de {origem} (seq={seq})")
                
            # Adiciona informação de quem enviou este LSA para evitar loops
            if "ultimo_salto" not in pacote:
                # Tenta encontrar o ID do roteador baseado no endereço IP
                ip_origem = endereco[0]
                id_origem = None
                for id_rot, mapa_ips in self.id_para_ip.items():
                    for vizinho_id, ip in mapa_ips.items():
                        if ip == ip_origem:
                            id_origem = vizinho_id
                            break
                    if id_origem:
                        break
                
                if id_origem:
                    pacote["ultimo_salto"] = id_origem
                else:
                    print(f"[{self.nome}] ⚠ Não foi possível determinar ID do roteador com IP {ip_origem}")
                    pacote["ultimo_salto"] = -1  # Valor inválido para identificar problema
            
            self.repassar_lsa(pacote)
            
            # Mover o cálculo de rotas para depois do repasse do LSA para evitar deadlocks
            with self.lock:
                self.calcular_rotas()

        elif pacote["tipo"] == "HELLO":
            print(f"[{self.nome}] Recebeu HELLO de {pacote['origem']} ({self.id_para_nome.get(pacote['origem'], 'desconhecido')})")

    def calcular_rotas(self):
        print(f"[{self.nome}] 🔍 Iniciando cálculo de rotas...")
        grafo = {}
        
        # Construir grafo a partir do LSDB
        for origem, dados in self.lsdb.items():
            if "vizinhos" in dados:  # Verificar se o campo vizinhos existe
                grafo[origem] = {v["id"]: v["custo"] for v in dados["vizinhos"]}
            else:
                print(f"[{self.nome}] ⚠ LSDB para origem {origem} não contém informações de vizinhos!")
        
        print(f"[{self.nome}] 🌐 Grafo atual: {grafo}")

        # Verificar se o grafo está vazio
        if not grafo:
            print(f"[{self.nome}] ⚠ Grafo vazio! Não é possível calcular rotas.")
            return

        todos_nos = set(grafo.keys())
        for vizinhos in grafo.values():
            todos_nos.update(vizinhos.keys())

        dist = {n: float("inf") for n in todos_nos}
        dist[self.id] = 0
        anterior = {}

        fila = [(0, self.id)]

        while fila:
            custo, atual = heapq.heappop(fila)
            
            # Verificar se o nó atual existe no grafo
            if atual not in grafo:
                continue
                
            for vizinho, peso in grafo.get(atual, {}).items():
                if dist[vizinho] > custo + peso:
                    dist[vizinho] = custo + peso
                    anterior[vizinho] = atual
                    heapq.heappush(fila, (dist[vizinho], vizinho))

        print(f"[{self.nome}] 🗺️ Tabela de distâncias (Dijkstra): {dist}")

        tabela = {}
        for destino in todos_nos:
            if destino == self.id:
                continue
            if destino not in anterior and destino != self.id:
                print(f"[{self.nome}] ⚠ Destino {destino} não alcançável")
                continue
                
            prox = destino
            while anterior.get(prox) != self.id and prox in anterior:
                prox = anterior[prox]
            if prox in anterior or anterior.get(prox) == self.id:
                tabela[destino] = prox

        if tabela != self.tabela_rotas:
            print(f"[{self.nome}] 📡 Tabela de roteamento atualizada: {tabela}")
            self.tabela_rotas = tabela
            self.instalar_rotas()
        else:
            print(f"[{self.nome}] 💤 Nenhuma mudança na tabela de roteamento.")

        for dest, prox in tabela.items():
            print(f"  Destino: {dest} → Próximo: {prox} (Custo: {dist[dest]})")

    def instalar_rotas(self):
        print(f"[{self.nome}] 🚧 Instalando rotas...")

        # Para cada roteador, instala rotas para sua rede de hosts
        rotas_desejadas = {}
        
        # Mapeamento de roteadores para suas redes de hosts
        roteador_para_rede = {
            1: "192.168.1.0/24",  # r1 hosts network
            2: "192.168.2.0/24",  # r2 hosts network 
            3: "192.168.3.0/24",  # r3 hosts network
            4: "192.168.4.0/24",  # r4 hosts network
            5: "192.168.5.0/24",  # r5 hosts network
        }
        
        # Para cada destino na tabela de rotas
        for destino, proximo in self.tabela_rotas.items():
            if destino in roteador_para_rede:
                destino_rede = roteador_para_rede[destino]
                rotas_desejadas[destino_rede] = proximo
        
        # Determina rotas para remover
        destinos_atuais = set(rotas_desejadas.keys())
        rotas_para_remover = self.rotas_instaladas - destinos_atuais

        # Remove rotas obsoletas
        for rota in rotas_para_remover:
            print(f"[{self.nome}] ❌ Removendo rota obsoleta: {rota}")
            subprocess.run(f"ip route del {rota}",
                           shell=True, stderr=subprocess.DEVNULL)

        # Instala novas rotas
        for destino_rede, proximo in rotas_desejadas.items():
            # Encontra o IP do próximo salto
            if self.id in self.id_para_ip and proximo in self.id_para_ip[self.id]:
                via_ip = self.id_para_ip[self.id][proximo]
                
                # Verifica se a rota já existe
                cmd_show = subprocess.run(
                    f"ip route show {destino_rede}", shell=True, capture_output=True, text=True)
                rota_existente = cmd_show.stdout.strip()

                if rota_existente and via_ip not in rota_existente:
                    subprocess.run(
                        f"ip route del {destino_rede}", shell=True, stderr=subprocess.DEVNULL)
                    rota_existente = ""

                if not rota_existente:
                    cmd_add = f"ip route add {destino_rede} via {via_ip}"
                    resultado = subprocess.run(
                        cmd_add, shell=True, capture_output=True)
                    if resultado.returncode == 0:
                        print(
                            f"[{self.nome}] ✅ Rota adicionada com sucesso: {destino_rede} via {via_ip}")
                    else:
                        print(
                            f"[{self.nome}] ❌ Falha ao adicionar rota: {resultado.stderr.decode()}")
            else:
                print(f"[{self.nome}] ⚠ Não foi possível determinar IP para o próximo salto {proximo}")

        self.rotas_instaladas = destinos_atuais
        print(f"[{self.nome}] 📦 Rotas instaladas agora: {self.rotas_instaladas}")

    def iniciar(self):
        print(f"[{self.nome}] Iniciando roteador...")
        threading.Thread(target=self.receber, daemon=True).start()
        threading.Thread(target=self.enviar_lsa, daemon=True).start()
        threading.Thread(target=self.enviar_hello, daemon=True).start()
        while True:
            time.sleep(1)

if __name__ == "__main__":
    ativar_ip_forward()
    
    # Obtém o nome do container da variável de ambiente
    container_name = os.environ.get('CONTAINER_NAME', socket.gethostname())
    print(f"Iniciando roteador com nome: {container_name}")
    
    roteador = Roteador(container_name)
    roteador.iniciar()