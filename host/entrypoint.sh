#!/bin/sh

# Aguarda a interface eth0 estar pronta (opcional mas recomendado)
sleep 1

# Descobre o IP da interface eth0
IP=$(ip -4 addr show eth0 | grep -oE 'inet ([0-9.]+)' | awk '{print $2}' | cut -d/ -f1)

# Verifica se o IP foi obtido
if [ -z "$IP" ]; then
  echo "❌ Não foi possível obter o IP da interface eth0"
  exit 1
fi

# Calcula o gateway assumindo IP final .2
GATEWAY=$(echo "$IP" | awk -F. '{print $1"."$2"."$3".2"}')

# Remove rota default existente e adiciona a nova
ip route del default 2>/dev/null
ip route add default via "$GATEWAY"

echo "✅ Gateway padrão configurado para $GATEWAY"

# Mantém o container vivo
exec tail -f /dev/null
