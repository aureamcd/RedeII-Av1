#!/bin/bash

# Verifica conectividade básica entre todos os hosts
echo "Testando conectividade entre hosts..."

# Lista de hosts
hosts=("r1_h1" "r1_h2" "r2_h1" "r2_h2" "r3_h1" "r3_h2" "r4_h1" "r4_h2" "r5_h1" "r5_h2")

for origem in "${hosts[@]}"; do
    for destino in "${hosts[@]}"; do
        if [ "$origem" != "$destino" ]; then
            # Obtém IP do destino
            ip_destino=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $destino)
            
            echo -n "$origem -> $destino ($ip_destino)... "
            
            # Testa conectividade
            if docker exec $origem ping -c 3 -W 1 $ip_destino >/dev/null 2>&1; then
                echo "✅ OK"
            else
                echo "❌ FALHOU"
            fi
        fi
    done
done