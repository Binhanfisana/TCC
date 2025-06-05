#!/bin/bash
# Limpeza
sudo pkill -f ryu-manager
sudo mn -c

# Inicia Ryu em background com redirecionamento de logs
ryu-manager --ofp-tcp-listen-port 6653 \
    ryu.app.simple_switch_13 \
    > /tmp/ryu.log 2>&1 &

# Espera 3 segundos para o controlador iniciar
sleep 3

# Verifica se o Ryu está rodando
if ! pgrep -f "ryu-manager" > /dev/null; then
    echo "ERRO: Ryu não iniciou. Verifique /tmp/ryu.log"
    exit 1
fi

# Inicia a topologia
sudo python3 topologia_gateway.py
