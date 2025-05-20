# generate_topology.py

import networkx as nx
import random
import json
import os
import matplotlib.pyplot as plt

NUM_ROTEADORES = 5

# Criar grafo parcialmente conectado
G = nx.connected_watts_strogatz_graph(NUM_ROTEADORES, k=2, p=0.5)

# Atribuir pesos (custos aleatórios) às arestas
for u, v in G.edges():
    G[u][v]['weight'] = random.randint(1, 10)

# Criar diretório para saída
os.makedirs("topologia", exist_ok=True)

# Salvar dados de cada roteador
for node in G.nodes():
    vizinhos = []
    for vizinho in G.neighbors(node):
        peso = G[node][vizinho]['weight']
        vizinhos.append({'id': vizinho, 'custo': peso})
    
    with open(f"topologia/roteador_{node}.json", "w") as f:
        json.dump({"id": node, "vizinhos": vizinhos}, f, indent=2)

# Também salva grafo completo (opcional)
nx.write_edgelist(G, "topologia/grafo.edgelist")



# Carrega o grafo salvo ou usa o G já criado
# Se estiver num script separado:
# G = nx.read_edgelist("topologia/grafo.edgelist", nodetype=int, data=(("weight", int),))

pos = nx.spring_layout(G, seed=42)  # Layout com espaçamento automático e fixo

# Desenha os nós e arestas
nx.draw(G, pos, with_labels=True, node_color="skyblue", node_size=1200, font_weight="bold")

# Desenha os pesos das arestas
labels = nx.get_edge_attributes(G, 'weight')
nx.draw_networkx_edge_labels(G, pos, edge_labels=labels)

plt.title("Topologia da Rede de Roteadores")
plt.show()
plt.savefig("topologia/diagrama_rede.png")

