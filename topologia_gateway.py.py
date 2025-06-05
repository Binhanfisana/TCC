#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch, Node, DefaultController
from mininet.link import TCLink
from mininet.log import setLogLevel, info, error
from mininet.cli import CLI
import time
import subprocess
import os

class DockerHost(Node):
    """Host Docker customizado com funções NFV"""
    def __init__(self, name, dimage='alpine', **kwargs):
        super(DockerHost, self).__init__(name, **kwargs)
        self.dimage = dimage
        
    def start(self):
        super(DockerHost, self).start()
        self.cmd('apk update && apk add --no-cache iptables curl tcpdump')

class TopoComGateway(Topo):
    """Topologia bcom SDN e NFV"""
    def build(self):
        # Switches
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')

        # Hosts - Organizados por sub-rede
        # Rede 10.0.1.0/24 (conectados ao s1)
        h1 = self.addHost('h1', ip='10.0.1.1/24', defaultRoute='via 10.0.1.254')
        h2 = self.addHost('h2', ip='10.0.1.2/24', defaultRoute='via 10.0.1.254')
        h6 = self.addHost('h6', ip='10.0.1.3/24', defaultRoute='via 10.0.1.254')
        h10 = self.addHost('h10', ip='10.0.1.4/24', defaultRoute='via 10.0.1.254')
        h11 = self.addHost('h11', ip='10.0.1.5/24', defaultRoute='via 10.0.1.254')
        h12 = self.addHost('h12', ip='10.0.1.6/24', defaultRoute='via 10.0.1.254')
        h9 = self.addHost('h9', ip='10.0.1.7/24', defaultRoute='via 10.0.1.254')

        # Rede 10.0.2.0/24 (conectados ao s2)
        h3 = self.addHost('h3', ip='10.0.2.1/24', defaultRoute='via 10.0.2.254')
        h4 = self.addHost('h4', ip='10.0.2.2/24', defaultRoute='via 10.0.2.254')
        h5 = self.addHost('h5', ip='10.0.2.3/24', defaultRoute='via 10.0.2.254')
        h7 = self.addHost('h7', ip='10.0.2.4/24', defaultRoute='via 10.0.2.254')
        h8 = self.addHost('h8', ip='10.0.2.5/24', defaultRoute='via 10.0.2.254')

        # Conexões - Organizadas por switch
        # Switch s1
        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h6, s1)
        self.addLink(h10, s1)
        self.addLink(h11, s1)
        self.addLink(h12, s1)
        self.addLink(h9, s1)

        # Switch s2
        self.addLink(h3, s2)
        self.addLink(h4, s2)
        self.addLink(h5, s2)
        self.addLink(h7, s2)
        self.addLink(h8, s2)

        # Roteador principal (Docker)
        r1 = self.addHost('r1', cls=DockerHost)
        self.addLink(r1, s1, intfName1='r1-eth0', params1={'ip': '10.0.1.254/24'})
        self.addLink(r1, s2, intfName1='r1-eth1', params1={'ip': '10.0.2.254/24'})

def configurar_nfv(net):
    """Configuração robusta do NAT e roteamento"""
    r1 = net.get('r1')
    info('\n*** Configurando NFV no roteador r1:\n')
    
    # Configuração das interfaces
    r1.cmd('ifconfig r1-eth0 10.0.1.254 netmask 255.255.255.0 up')
    r1.cmd('ifconfig r1-eth1 10.0.2.254 netmask 255.255.255.0 up')
    
    # Habilita forwarding
    r1.cmd('sysctl -w net.ipv4.ip_forward=1')
    
    # Configuração do NAT
    r1.cmd('iptables -t nat -F')
    r1.cmd('iptables -t nat -A POSTROUTING -o r1-eth1 -j MASQUERADE')
    
    # Regras de firewall
    r1.cmd('iptables -F')
    r1.cmd('iptables -P FORWARD ACCEPT')
    r1.cmd('iptables -A FORWARD -i r1-eth0 -o r1-eth1 -j ACCEPT')
    r1.cmd('iptables -A FORWARD -i r1-eth1 -o r1-eth0 -m state --state RELATED,ESTABLISHED -j ACCEPT')
    
    # Verificação
    info('\n*** Configuração atual:\n')
    info(r1.cmd('route -n'))
    info(r1.cmd('iptables -t nat -L -v'))
    info(r1.cmd('iptables -L -v'))

def run():
    setLogLevel('info')
    
    # Limpeza
    os.system('sudo mn -c')
    os.system('sudo pkill -f ryu-manager')
    time.sleep(2)
    
    try:
        net = Mininet(topo=TopoComGateway(),
                     controller=DefaultController,
                     switch=OVSKernelSwitch,
                     link=TCLink,
                     autoSetMacs=True)
        
        net.start()
        configurar_nfv(net)
        
        # Testes de conectividade robustos
        info('\n=== Testando conectividade ===\n')
        h1, h3 = net.get('h1'), net.get('h3')
        
        # Teste ping com timeout aumentado
        info(h1.cmd('ping -c 3 -W 3 10.0.2.1'))
        
        # Teste completo
        info('\n=== Teste pingall ===\n')
        info(net.pingAll())
        
        CLI(net)
        
    except Exception as e:
        error(f'\n*** ERRO: {str(e)}\n')
        
        # Debug avançado
        error('\n=== Status das interfaces ===\n')
        for host in net.hosts:
            error(f"{host.name}:\n{host.cmd('ifconfig -a')}\n")
        
        error('\n=== Tabelas de roteamento ===\n')
        for host in net.hosts:
            error(f"{host.name}:\n{host.cmd('route -n')}\n")
        
    finally:
        if 'net' in locals():
            net.stop()

if __name__ == '__main__':
    run()
