#!/bin/bash

# Testa o tempo de convergência da rede após inicialização
echo "Iniciando teste de convergência..."

# Reinicia todos os containers para garantir estado limpo
echo "Reiniciando containers..."
docker-compose down
docker-compose up -d

# Lista de roteadores
roteadores=("r1" "r2" "r3" "r4" "r5")

# Aguarda inicialização
echo "Aguardando inicialização dos roteadores (10 segundos)..."
sleep 10

# Monitora estabilização das tabelas de roteamento
echo "Monitorando convergência..."
start_time=$(date +%s)
convergiu=0

while [ $convergiu -eq 0 ]; do
    convergiu=1
    for rot in "${roteadores[@]}"; do
        # Verifica se todas as rotas estão instaladas
        count=$(docker exec $rot ip route | grep -c "via")
        if [ $count -lt 4 ]; then  # Espera-se pelo menos 4 rotas (para 5 roteadores)
            convergiu=0
            break
        fi
    done
    sleep 1
done

end_time=$(date +%s)
duration=$((end_time - start_time))

echo "----------------------------------------"
echo "REDE CONVERGIU EM $duration SEGUNDOS"
echo "----------------------------------------"

# Gera relatório
echo "Tempo de convergência: $duration segundos" > relatorio_convergencia.txt
echo "Status final:" >> relatorio_convergencia.txt
for rot in "${roteadores[@]}"; do
    echo "=== $rot ===" >> relatorio_convergencia.txt
    docker exec $rot ip route >> relatorio_convergencia.txt
done

echo "Relatório salvo em relatorio_convergencia.txt"