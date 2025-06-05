#!/bin/bash

echo "=============================="
echo "⚡ Configurando Roteador r1..."
echo "=============================="
r1 ifconfig r1-eth0 10.0.1.254/24
r1 ifconfig r1-eth1 10.0.2.254/24
r1 sysctl -w net.ipv4.ip_forward=1

echo "=============================="
echo "⚡ Configurando Hosts da rede 10.0.1.0/24..."
echo "=============================="
h1 ifconfig h1-eth0 10.0.1.1/24
h2 ifconfig h2-eth0 10.0.1.2/24
h6 ifconfig h6-eth0 10.0.1.3/24
h10 ifconfig h10-eth0 10.0.1.4/24
h11 ifconfig h11-eth0 10.0.1.5/24
h12 ifconfig h12-eth0 10.0.1.6/24
h9 ifconfig h9-eth0 10.0.1.7/24

h1 route add default gw 10.0.1.254
h2 route add default gw 10.0.1.254
h6 route add default gw 10.0.1.254
h10 route add default gw 10.0.1.254
h11 route add default gw 10.0.1.254
h12 route add default gw 10.0.1.254
h9 route add default gw 10.0.1.254

echo "=============================="
echo "⚡ Configurando Hosts da rede 10.0.2.0/24..."
echo "=============================="
h3 ifconfig h3-eth0 10.0.2.1/24
h4 ifconfig h4-eth0 10.0.2.2/24
h5 ifconfig h5-eth0 10.0.2.3/24
h7 ifconfig h7-eth0 10.0.2.4/24
h8 ifconfig h8-eth0 10.0.2.5/24

h3 route add default gw 10.0.2.254
h4 route add default gw 10.0.2.254
h5 route add default gw 10.0.2.254
h7 route add default gw 10.0.2.254
h8 route add default gw 10.0.2.254

echo "=============================="
echo "✅ Rede configurada com sucesso!"
echo "Pronto para iniciar os testes de conectividade e desempenho!"
echo "=============================="
