#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch, Node
from mininet.link import TCLink
from mininet.log import setLogLevel, info, error
from mininet.cli import CLI
import time
import subprocess
import os
import json

class EnhancedDockerHost(Node):
    def __init__(self, name, dimage='alpine', **kwargs):
        super().__init__(name, **kwargs)   
        self.dimage = dimage

    def start(self):
        super().start()
        self.cmd(
            '(apk update && apk add --no-cache iptables curl tcpdump conntrack-tools traceroute) || '
            '(apt-get update && apt-get install -y iptables curl tcpdump conntrack traceroute) || '
            f'echo "\\033[91m[⚠️  Falha]\\033[0m Não foi possível instalar pacotes no gateway \\033[93m{self.name}\\033[0m."'
        )
        info(f'\n🟢 Gateway \033[92m{self.name}\033[0m inicializado com pacotes essenciais instalados.')


class RobustTopo(Topo):
    def build(self):
        s1 = self.addSwitch('s1', cls=OVSKernelSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSKernelSwitch, protocols='OpenFlow13')

        hosts_s1 = [
            ('h1', '10.0.1.1'), ('h2', '10.0.1.2'), ('h6', '10.0.1.3'),
            ('h10', '10.0.1.4'), ('h11', '10.0.1.5'), ('h12', '10.0.1.6'),
            ('h9', '10.0.1.7')
        ]

        hosts_s2 = [
            ('h3', '10.0.2.1'), ('h4', '10.0.2.2'), ('h5', '10.0.2.3'),
            ('h7', '10.0.2.4'), ('h8', '10.0.2.5')
        ]

        for name, ip in hosts_s1:
            self.addHost(name, ip=f'{ip}/24', defaultRoute='via 10.0.1.254')
            self.addLink(name, s1)

        for name, ip in hosts_s2:
            self.addHost(name, ip=f'{ip}/24', defaultRoute='via 10.0.2.254')
            self.addLink(name, s2)

        r1 = self.addHost('r1', cls=EnhancedDockerHost)
        self.addLink(r1, s1, intfName1='r1-eth0', params1={'ip': '10.0.1.254/24'})
        self.addLink(r1, s2, intfName1='r1-eth1', params1={'ip': '10.0.2.254/24'})
        info('\n🛡️  Gateway \033[92mr1\033[0m conectado com sucesso aos switches \033[94ms1\033[0m e \033[94ms2\033[0m.')


def configure_nfv(net):
    r1 = net.get('r1')

    r1.cmd('ip link set dev r1-eth0 up')
    r1.cmd('ip link set dev r1-eth1 up')
    r1.cmd('ip addr add 10.0.1.254/24 dev r1-eth0')
    r1.cmd('ip addr add 10.0.2.254/24 dev r1-eth1')

    r1.cmd('echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-ipforward.conf')
    r1.cmd('sysctl -p /etc/sysctl.d/99-ipforward.conf')

    r1.cmd('iptables -t nat -F')
    r1.cmd('iptables -t nat -A POSTROUTING -o r1-eth1 -j MASQUERADE')
    r1.cmd('iptables -t nat -A POSTROUTING -o r1-eth1 -j LOG --log-prefix "NAT: "')

    r1.cmd('iptables -F')
    r1.cmd('iptables -P FORWARD DROP')
    r1.cmd('iptables -A FORWARD -i r1-eth0 -o r1-eth1 -m conntrack --ctstate NEW -j ACCEPT')
    r1.cmd('iptables -A FORWARD -i r1-eth1 -o r1-eth0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT')

    r1.cmd('iptables -N LOGGING')
    r1.cmd('iptables -A FORWARD -j LOGGING')
    r1.cmd('iptables -A LOGGING -j LOG --log-prefix "FORWARD: " --log-level 4')
    r1.cmd('iptables -A LOGGING -j ACCEPT')

    r1.cmd('echo 1 > /proc/sys/net/ipv4/conf/all/log_martians')

    info("\n✅ Gateway NFV '\033[92mr1\033[0m' configurado com sucesso! Rede segura e rastreável.")
    info("\n=== \033[94mConfiguração de Rede\033[0m ===")
    info(r1.cmd('ip addr show'))
    info("\n=== \033[94mTabela de Roteamento\033[0m ===")
    info(r1.cmd('ip route show'))
    info("\n=== \033[94mRegras NAT\033[0m ===")
    info(r1.cmd('iptables -t nat -L -v -n'))
    info("\n=== \033[94mRegras de Firewall\033[0m ===")
    info(r1.cmd('iptables -L -v -n'))

def custom_cli(net):
    def addflow():
        sw = input("Switch destino (ex: s1): ").strip()
        flow_id = input("ID do fluxo: ").strip()
        ip_src = input("IP de origem: ").strip()
        ip_dst = input("IP de destino: ").strip()
        tp_src = input("Porta TCP de origem: ").strip()
        tp_dst = input("Porta TCP de destino: ").strip()

        cmd = [
            'ovs-ofctl', '-O', 'OpenFlow13', 'add-flow', sw,
            f"priority=100,ip,nw_src={ip_src},nw_dst={ip_dst},tcp,tp_src={tp_src},tp_dst={tp_dst},actions="
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"\033[91m🚫 Fluxo {flow_id}\033[0m adicionado em {sw}: Bloqueando {ip_src}:{tp_src} -> {ip_dst}:{tp_dst}")
        except subprocess.CalledProcessError as e:
            print("❌ Erro ao adicionar fluxo:", e)

    def showflows():
        sw = input("Switch para mostrar os fluxos (ex: s1): ").strip()
        try:
            output = subprocess.check_output(['ovs-ofctl', '-O', 'OpenFlow13', 'dump-flows', sw]).decode()
            print(f"📋 Fluxos ativos em {sw}:\n{output}")
        except subprocess.CalledProcessError as e:
            print("❌ Erro ao mostrar fluxos:", e)

    def add_dynamic_host():
        """Adiciona um novo host dinamicamente à rede."""
        info("\n=== Adicionar Novo Host Dinamicamente ===")
        host_name = input("Nome do novo host (ex: h13): ").strip()
        host_ip = input(f"IP do novo host (ex: 10.0.1.13/24 ou 10.0.2.10/24): ").strip()
        target_switch_name = input("Nome do switch ao qual conectar (s1 ou s2): ").strip()

        if not host_name or not host_ip or not target_switch_name:
            error("Todos os campos são obrigatórios.")
            return

        try:
            # Verifica se o host já existe
            if net.get(host_name):
                error(f"Host '{host_name}' já existe na rede.")
                return

            # Obtém o switch
            target_switch = net.get(target_switch_name)
            if not target_switch:
                error(f"Switch '{target_switch_name}' não encontrada na rede.")
                return

            info(f"Adicionando host '{host_name}' com IP '{host_ip}' ao switch '{target_switch_name}'...")
            
            # Determina a rota padrão baseada no IP
            default_route = ''
            if host_ip.startswith('10.0.1.'):
                default_route = 'via 10.0.1.254'
            elif host_ip.startswith('10.0.2.'):
                default_route = 'via 10.0.2.254'
            
            # Cria o host, mas ainda não o inicia no Mininet
            new_host = net.addHost(host_name, ip=host_ip, defaultRoute=default_route)
            
            # Conecta o link
            net.addLink(new_host, target_switch)
            
            # *** ESSA É A LINHA CRÍTICA ADICIONADA/MODIFICADA ***
            # Inicia o novo host como um processo Mininet separado e suas interfaces
            new_host.start() 
            # O Mininet já cuida de 'ifconfig up' automaticamente após o start()

            info(f"✅ Host '{host_name}' adicionado e conectado ao switch '{target_switch_name}' com sucesso!")
            info(f"Configuração IP de {host_name}: {new_host.cmd('ip addr show')}")

        except Exception as e:
            error(f"❌ Erro ao adicionar novo host: {e}")

    CLI.do_addflow = lambda self, args='': addflow()
    CLI.do_showflows = lambda self, args='': showflows()
    # Mudei de 'addhost' para 'addnode' para ser mais genérico caso queira adicionar outros tipos de nós futuramente
    CLI.do_addnode = lambda self, args='': add_dynamic_host() 
    
    CLI.help_addflow = lambda self: print("addflow: Adiciona um fluxo de bloqueio baseado em IP/portas TCP")
    CLI.help_showflows = lambda self: print("showflows: Lista todos os fluxos instalados em um switch")
    CLI.help_addnode = lambda self: print("addnode: Adiciona um novo host dinamicamente à rede (ex: addnode)") # Ajuda para o novo comando

    CLI(net)

def run():
    setLogLevel('info')
    os.system('sudo mn -c >/dev/null 2>&1')
    os.system('sudo pkill -f ryu-manager >/dev/null 2>&1')
    os.system('sudo pkill -f ovs-testcontroller >/dev/null 2>&1')
    time.sleep(2)

    try:
        net = Mininet(
            topo=RobustTopo(),
            controller=lambda name: RemoteController(name, ip='127.0.0.1', port=6653),
            switch=OVSKernelSwitch,
            link=TCLink,
            autoSetMacs=True,
            waitConnected=True,
            cleanup=True
        )

        net.start()
        info("\n🚀 Topologia ativa! Sistema SDN pronto para testes e bloqueios de tráfego.")
        configure_nfv(net)
        custom_cli(net)

    except Exception as e:
        error(f'\n*** ERRO: {str(e)}\n')

    finally:
        if 'net' in locals():
            info("\n🔻 Rede encerrada. Limpando ambiente...")
            net.stop()

if __name__ == '__main__':
    run()
