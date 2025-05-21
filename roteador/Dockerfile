# Dockerfile.router
FROM python:3.10-slim

# Instala os pacotes necessários para roteamento e diagnóstico
RUN apt update && apt install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    procps \
    && apt clean \
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
# Define o diretório de trabalho
WORKDIR /app

# Copia o código-fonte e topologia
COPY roteador.py ./roteador.py
COPY topologia /app/topologia

# Garante que estamos como root (para alterar rotas e IP forwarding)
USER root

# Comando padrão do container
CMD ["python3", "-u", "/app/roteador.py", "0"]
