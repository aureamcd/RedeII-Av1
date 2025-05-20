# Dockerfile.host
FROM alpine:latest

RUN apk add --no-cache iputils bash

# Copia o script de entrada
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Usa o script como ponto de entrada
CMD ["/entrypoint.sh"]
