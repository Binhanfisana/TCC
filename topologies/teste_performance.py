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
            '(apk update && apk add --no-cache iptables curl tcpdump conntrack-tools traceroute iproute2) || ' # Adicionado iproute2
            '(apt-get update && apt-get install -y iptables curl tcpdump conntrack traceroute iproute2) || ' # Adicionado iproute2
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
            ('h9', '10.0.1.7'),
            ('h13', '10.0.1.13') # Adicionado h13 na topologia inicial para facilitar o provisionamento
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

    r1.cmd('iptables -t nat -F') # Limpa todas as regras NAT existentes
    r1.cmd('iptables -t nat -A POSTROUTING -o r1-eth1 -j MASQUERADE')
    r1.cmd('iptables -t nat -A POSTROUTING -o r1-eth1 -j LOG --log-prefix "NAT: "')

    # Limpa todas as regras de FILTER (FORWAR, INPUT, OUTPUT) para começar limpo
    r1.cmd('iptables -F')
    r1.cmd('iptables -X') # Remove cadeias personalizadas
    r1.cmd('iptables -P INPUT ACCEPT') # Define políticas padrão para ACCEPT antes de limpar FORWARD
    r1.cmd('iptables -P OUTPUT ACCEPT')
    r1.cmd('iptables -P FORWARD DROP') # Policy DROP para FORWARD como padrão de segurança

    # Cria e aplica a cadeia LOGGING (se não existir)
    r1.cmd('iptables -N LOGGING 2>/dev/null || true') # || true para evitar erro se já existir
    r1.cmd('iptables -F LOGGING') # Limpa a cadeia LOGGING

    r1.cmd('iptables -A FORWARD -i r1-eth0 -o r1-eth1 -m conntrack --ctstate NEW -j ACCEPT')
    r1.cmd('iptables -A FORWARD -i r1-eth1 -o r1-eth0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT')
    
    r1.cmd('iptables -A FORWARD -j LOGGING') # Adiciona a regra de logging ao FORWARD
    r1.cmd('iptables -A LOGGING -j LOG --log-prefix "FORWARD: " --log-level 4')
    r1.cmd('iptables -A LOGGING -j ACCEPT') # Permite o tráfego após o log na cadeia LOGGING

    r1.cmd('echo 1 > /proc/sys/net/ipv4/conf/all/log_martians')

    info("\n✅ Gateway NFV '\033[92mr1\033[0m' configurado com sucesso! Rede segura e rastreável.")
    info("\n=== \033[94mConfiguração de Rede\033[0m ===")
    info(r1.cmd('ip addr show'))
    info("\n=== \033[94mTabela de Roteamento\033[0m ===")
    info(r1.cmd('ip route show'))
    info("\n=== \033[94mRegras NAT\033[0m ===")
    info(r1.cmd('iptables -t nat -L -v -n'))
    info("\n=== \033[94mRegras de Firewall (Padrão)\033[0m ===")
    info(r1.cmd('iptables -L -v -n'))

def custom_cli(net):
    # --- Comandos Existentes ---
    def addflow():
        sw = input("Switch destino (ex: s1): ").strip()
        flow_id = input("ID do fluxo: ").strip()
        ip_src = input("IP de origem (ex: 10.0.1.1/32 ou any): ").strip()
        ip_dst = input("IP de destino (ex: 10.0.2.1/32 ou any): ").strip()
        tp_src = input("Porta TCP de origem (0 para qualquer): ").strip()
        tp_dst = input("Porta TCP de destino (0 para qualquer): ").strip()

        cmd = [
            'sudo', 'ovs-ofctl', '-O', 'OpenFlow13', 'add-flow', sw,
            f"priority=100,ip"
        ]
        if ip_src.lower() != 'any': cmd.append(f"nw_src={ip_src}")
        if ip_dst.lower() != 'any': cmd.append(f"nw_dst={ip_dst}")
        cmd.append(f"tcp,tp_src={tp_src},tp_dst={tp_dst},actions=drop") # Ação padrão drop para o seu caso

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            info(f"\033[91m🚫 Fluxo {flow_id}\033[0m adicionado em {sw}: Bloqueando {ip_src}:{tp_src} -> {ip_dst}:{tp_dst}")
        except subprocess.CalledProcessError as e:
            error(f"❌ Erro ao adicionar fluxo: {e.stderr}\nComando: {' '.join(cmd)}")
        except Exception as e:
            error(f"❌ Erro inesperado: {e}")

    def showflows():
        sw = input("Switch para mostrar os fluxos (ex: s1): ").strip()
        try:
            output = subprocess.check_output(['sudo', 'ovs-ofctl', '-O', 'OpenFlow13', 'dump-flows', sw]).decode()
            info(f"📋 Fluxos ativos em {sw}:\n{output}")
        except subprocess.CalledProcessError as e:
            error(f"❌ Erro ao mostrar fluxos: {e.stderr}")

    # --- Medição de Desempenho ---
    def run_ping_test():
        info("\n=== Teste de Ping ===")
        src_host_name = input("Host de origem (ex: h1): ").strip()
        dst_host_name = input("Host de destino (ex: h3): ").strip()
        count = input("Número de pings (padrão 4): ").strip() or "4"
        
        src_host = net.get(src_host_name)
        dst_host = net.get(dst_host_name)

        if not src_host or not dst_host:
            error("Host(s) não encontrado(s).")
            return
        
        info(f"Iniciando ping de {src_host.name} para {dst_host.name} ({dst_host.IP()})...")
        cmd = f"ping -c {count} {dst_host.IP()}"
        output = src_host.cmd(cmd)
        info(f"\n--- Resultados do Ping ({src_host.name} para {dst_host.name}) ---\n{output}")

    def run_iperf_test():
        info("\n=== Teste de iPerf3 ===")
        server_host_name = input("Host Servidor iPerf (ex: h3): ").strip()
        client_host_name = input("Host Cliente iPerf (ex: h1): ").strip()
        duration = input("Duração do teste em segundos (padrão 10): ").strip() or "10"

        server_host = net.get(server_host_name)
        client_host = net.get(client_host_name)

        if not server_host or not client_host:
            error("Host(s) não encontrado(s).")
            return
        
        info(f"Configurando servidor iPerf3 em {server_host.name}...")
        server_host.cmd('iperf3 -s &') # Inicia iPerf3 server em background

        info(f"Iniciando cliente iPerf3 de {client_host.name} para {server_host.name} ({server_host.IP()})...")
        client_cmd = f"iperf3 -c {server_host.IP()} -t {duration}"
        client_output = client_host.cmd(client_cmd)
        
        info(f"\n--- Resultados do iPerf3 ({client_host.name} para {server_host.name}) ---\n{client_output}")
        
        info(f"Parando servidor iPerf3 em {server_host.name}...")
        server_host.cmd('pkill iperf3') # Mata o processo iPerf3 server

    # --- Firewall Dinâmico no R1 (NFV) ---
    def r1_add_fw_rule():
        info("\n=== Adicionar Regra de Firewall no R1 ===")
        r1 = net.get('r1')
        if not r1:
            error("Gateway r1 não encontrado.")
            return

        print("Escolha o tipo de regra:")
        print("1 - Bloquear IP de Origem (DROP SRC_IP)")
        print("2 - Bloquear IP de Destino (DROP DST_IP)")
        print("3 - Bloquear Porta TCP de Destino (DROP TCP_DST_PORT)")
        print("4 - Bloquear Porta UDP de Destino (DROP UDP_DST_PORT)")
        rule_type = input("Opção: ").strip()

        rule_cmd = ""
        if rule_type == '1':
            src_ip = input("IP de Origem a bloquear (ex: 10.0.1.1): ").strip()
            rule_cmd = f"iptables -A FORWARD -s {src_ip} -j DROP"
        elif rule_type == '2':
            dst_ip = input("IP de Destino a bloquear (ex: 10.0.2.1): ").strip()
            rule_cmd = f"iptables -A FORWARD -d {dst_ip} -j DROP"
        elif rule_type == '3':
            dst_ip = input("IP de Destino (opcional, 'any' para qualquer): ").strip() or '0.0.0.0/0'
            dst_port = input("Porta TCP de Destino a bloquear (ex: 80): ").strip()
            rule_cmd = f"iptables -A FORWARD -p tcp --dport {dst_port} -d {dst_ip} -j DROP"
        elif rule_type == '4':
            dst_ip = input("IP de Destino (opcional, 'any' para qualquer): ").strip() or '0.0.0.0/0'
            dst_port = input("Porta UDP de Destino a bloquear (ex: 53): ").strip()
            rule_cmd = f"iptables -A FORWARD -p udp --dport {dst_port} -d {dst_ip} -j DROP"
        else:
            error("Opção inválida.")
            return
        
        info(f"Aplicando regra no r1: {rule_cmd}")
        output = r1.cmd(rule_cmd)
        if "Bad argument" in output or "iptables: " in output:
            error(f"❌ Erro ao adicionar regra no r1: {output}")
        else:
            info("✅ Regra de firewall adicionada com sucesso no r1.")

    def r1_clear_fw():
        info("\n=== Limpar Regras de Firewall do R1 ===")
        r1 = net.get('r1')
        if not r1:
            error("Gateway r1 não encontrado.")
            return
        
        confirm = input("Tem certeza que deseja limpar TODAS as regras FORWARD do r1? (s/N): ").lower()
        if confirm == 's':
            # Assegura que as regras básicas de conntrack sejam mantidas ou recriadas
            r1.cmd('iptables -F FORWARD') # Limpa apenas a cadeia FORWARD
            r1.cmd('iptables -D FORWARD -j LOGGING 2>/dev/null || true') # Remove a regra de logging se existir
            r1.cmd('iptables -D LOGGING -j LOG --log-prefix "FORWARD: " --log-level 4 2>/dev/null || true')
            r1.cmd('iptables -D LOGGING -j ACCEPT 2>/dev/null || true')

            # Recria as regras essenciais de encaminhamento e logging
            r1.cmd('iptables -A FORWARD -i r1-eth0 -o r1-eth1 -m conntrack --ctstate NEW -j ACCEPT')
            r1.cmd('iptables -A FORWARD -i r1-eth1 -o r1-eth0 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT')
            r1.cmd('iptables -A FORWARD -j LOGGING') # Adiciona a regra de logging de volta
            info("✅ Regras FORWARD do r1 limpas e regras básicas restauradas.")
        else:
            info("Operação cancelada.")

    def r1_show_fw():
        info("\n=== Mostrar Regras de Firewall do R1 ===")
        r1 = net.get('r1')
        if not r1:
            error("Gateway r1 não encontrado.")
            return
        
        output = r1.cmd('iptables -L FORWARD -v -n')
        info(f"\n--- Regras de Firewall FORWARD no r1 ---\n{output}")

    # --- Registro de Comandos na CLI ---
    CLI.do_addflow = lambda self, args='': addflow()
    CLI.do_showflows = lambda self, args='': showflows()
    CLI.do_pingtest = lambda self, args='': run_ping_test()
    CLI.do_iperftest = lambda self, args='': run_iperf_test()
    CLI.do_r1addfw = lambda self, args='': r1_add_fw_rule()
    CLI.do_r1clearfw = lambda self, args='': r1_clear_fw()
    CLI.do_r1showfw = lambda self, args='': r1_show_fw()

    CLI.help_addflow = lambda self: print("addflow: Adiciona um fluxo de bloqueio em um switch (SDN).")
    CLI.help_showflows = lambda self: print("showflows: Lista todos os fluxos instalados em um switch.")
    CLI.help_pingtest = lambda self: print("pingtest: Realiza teste de ping entre dois hosts.")
    CLI.help_iperftest = lambda self: print("iperftest: Realiza teste de iPerf3 entre dois hosts.")
    CLI.help_r1addfw = lambda self: print("r1addfw: Adiciona uma regra de firewall (DROP) na cadeia FORWARD do gateway r1 (NFV).")
    CLI.help_r1clearfw = lambda self: print("r1clearfw: Limpa todas as regras de FORWARD do iptables no r1, restaurando as básicas.")
    CLI.help_r1showfw = lambda self: print("r1showfw: Exibe as regras de firewall (FORWARD) atualmente configuradas no r1.")

    CLI(net)

def run():
    setLogLevel('info')
    info("Limpeza de ambientes anteriores...")
    os.system('sudo mn -c >/dev/null 2>&1')
    os.system('sudo pkill -f ryu-manager >/dev/null 2>&1')
    os.system('sudo pkill -f ovs-testcontroller >/dev/null 2>&1')
    time.sleep(2)
    info("Limpeza concluída.")

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
        import traceback
        traceback.print_exc() # Imprime o stack trace para depuração

    finally:
        if 'net' in locals():
            info("\n🔻 Rede encerrada. Limpando ambiente...")
            net.stop()

if __name__ == '__main__':
    run()
