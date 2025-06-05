#!/bin/bash
# testar_desempenho.sh - Versão corrigida para Mininet

ARQUIVO="/tmp/resultados_teste.csv"
echo "Teste,Origem,Destino,Metrica,Valor" > $ARQUIVO

# Hosts das redes
hosts1=(h1 h2 h6 h10 h11 h12 h9)
hosts2=(h3 h4 h5 h7 h8)

# Testes PING
for src in "${hosts1[@]}"; do
    for dst in "${hosts2[@]}"; do
        echo "🔵 Ping: $src -> $dst"
        # Sintaxe correta para Mininet:
        rtt=$(ping -c 3 -W 3 ${dst}-eth0 | tail -1 | awk -F'/' '{print $5}')
        if [ -z "$rtt" ]; then rtt=0; fi
        echo "Ping,$src,$dst,RTT(ms),$rtt" >> $ARQUIVO
    done
done

# Testes IPERF
for src in "${hosts1[@]}"; do
    for dst in "${hosts2[@]}"; do
        echo "🔴 Iperf: $src -> $dst"
        # Inicia servidor no destino
        echo "Iniciando servidor iperf em $dst"
        # Executa cliente na origem
        bw=$(iperf -t 5 -c ${dst}-eth0 -p 5001 -i 1 | grep 'Mbits/sec' | tail -1 | awk '{print $7}')
        if [ -z "$bw" ]; then bw=0; fi
        echo "Iperf,$src,$dst,Banda(Mbps),$bw" >> $ARQUIVO
    done
done

echo "✅ Resultados salvos em $ARQUIVO"

