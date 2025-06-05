import os
import subprocess # Usar subprocess para melhor tratamento de erros

def clear():
    """Limpa a tela do terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')

def adicionar_fluxo():
    """Permite ao usuário adicionar um fluxo de bloqueio OpenFlow."""
    clear()
    print("=== Adicionar Novo Fluxo de Bloqueio ===")
    switch = input("SWITCH (ex: s1 ou s2): ").strip()
    flow_id = input("ID do Fluxo (ex: block_http_h1): ").strip()
    priority = input("PRIORIDADE (número, ex: 100): ").strip()
    src_ip = input("IP DE ORIGEM (ex: 10.0.1.1/32 ou any): ").strip()
    dst_ip = input("IP DE DESTINO (ex: 10.0.2.1/32 ou any): ").strip()
    src_port = input("PORTA DE ORIGEM (TCP, ex: 80 ou 0 para qualquer): ").strip()
    dst_port = input("PORTA DE DESTINO (TCP, ex: 80 ou 0 para qualquer): ").strip()

    # Construção do comando ovs-ofctl
    cmd_parts = [
        "sudo", "ovs-ofctl", "-O", "OpenFlow13", "add-flow", switch,
        f"priority={priority},ip"
    ]

    if src_ip.lower() != 'any':
        cmd_parts.append(f"nw_src={src_ip}")
    if dst_ip.lower() != 'any':
        cmd_parts.append(f"nw_dst={dst_ip}")

    # Sempre incluir TCP mesmo que as portas sejam 0 para corresponder ao seu modelo de input
    cmd_parts.append(f"tcp,tp_src={src_port},tp_dst={dst_port},actions=drop")

    try:
        # Usar subprocess.run para melhor tratamento de erros
        subprocess.run(cmd_parts, check=True, capture_output=True, text=True)
        print(f"\n✅ Fluxo '{flow_id}' adicionado com sucesso ao switch '{switch}'! "
              f"Bloqueando {src_ip}:{src_port} -> {dst_ip}:{dst_port}.")
    except subprocess.CalledProcessError as e:
        print(f"\n Erro ao adicionar o fluxo '{flow_id}'. Detalhes do erro:")
        print(f"Comando executado: {' '.join(cmd_parts)}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
    except Exception as e:
        print(f"\n Ocorreu um erro inesperado: {e}")

    input("\nPressione Enter para continuar...")

def listar_fluxos():
    """Lista todos os fluxos OpenFlow em um switch especificado."""
    clear()
    print("=== Listar Fluxos ===")
    switch = input("Digite o nome do switch (s1 ou s2): ").strip()
    try:
        # Usar subprocess.run para melhor tratamento de erros e captura de output
        result = subprocess.run(
            ["sudo", "ovs-ofctl", "-O", "OpenFlow13", "dump-flows", switch],
            check=True, capture_output=True, text=True
        )
        print(f"\n Fluxos ativos em '{switch}':")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"\n Erro ao listar fluxos do switch '{switch}'. Detalhes do erro:")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
    except Exception as e:
        print(f"\n Ocorreu um erro inesperado: {e}")
    input("\nPressione Enter para continuar...")

def remover_fluxo():
    """Remove todos os fluxos OpenFlow de um switch especificado."""
    clear()
    print("=== Remover Fluxos ===")
    switch = input("Digite o nome do switch (s1 ou s2): ").strip()
    confirmacao = input(f"Tem certeza que deseja remover TODOS os fluxos de '{switch}'? (s/N): ").lower()
    if confirmacao == 's':
        try:
            subprocess.run(
                ["sudo", "ovs-ofctl", "-O", "OpenFlow13", "del-flows", switch],
                check=True, capture_output=True, text=True
            )
            print(f"\n✅ Todos os fluxos removidos de '{switch}' com sucesso!")
        except subprocess.CalledProcessError as e:
            print(f"\n Erro ao remover fluxos do switch '{switch}'. Detalhes do erro:")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
        except Exception as e:
            print(f"\n Ocorreu um erro inesperado: {e}")
    else:
        print("\nOperação de remoção de fluxos cancelada.")
    input("\nPressione Enter para continuar...")

def main():
    """Função principal que exibe o menu e gerencia as opções."""
    while True:
        clear()
        print("╔════════════════════════════╗")
        print("║ MENU - GERENCIAR FLOWS     ║")
        print("╠════════════════════════════╣")
        print("║ 1 - Listar fluxos          ║")
        print("║ 2 - Adicionar fluxo        ║")
        print("║ 3 - Remover fluxos         ║")
        print("║ 4 - Sair                   ║")
        print("╚════════════════════════════╝\n")
        opcao = input("Escolha uma opção: ").strip()

        if opcao == '1':
            listar_fluxos()
        elif opcao == '2':
            adicionar_fluxo()
        elif opcao == '3':
            remover_fluxo()
        elif opcao == '4':
            print("Saindo do gerenciador de fluxos. Até mais!")
            break
        else:
            print("Opção inválida. Por favor, escolha um número de 1 a 4.")
            input("\nPressione Enter para continuar...")

if __name__ == "__main__":
    main()
