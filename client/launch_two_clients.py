import argparse
import subprocess
import sys
import time
import signal
import os

DEFAULT_HOST  = "127.0.0.1"
DEFAULT_PORT  = 8888
DEFAULT_DELAY = 0.5          # opóźnienie (s) między uruchomieniem obu okien

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MAIN = os.path.join(_SCRIPT_DIR, "interface", "main.py")

def parse_args():
    p = argparse.ArgumentParser(
        description="Uruchamia dwóch klientów STMP jako osobne procesy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Klient 1
    g1 = p.add_argument_group("Klient 1")
    g1.add_argument("--host1",       default=None,           help=f"Host serwera dla Klienta-1 (domyślnie: {DEFAULT_HOST})")
    g1.add_argument("--port1",       default=None, type=int, help=f"Port serwera dla Klienta-1 (domyślnie: {DEFAULT_PORT})")
    g1.add_argument("--local-host1", default=None, dest="local_host1",
                    help="Lokalny interfejs sieciowy Klienta-1 (np. 127.0.0.1). "
                         "Domyślnie: system wybiera automatycznie.")
    g1.add_argument("--label1",      default="Klient-1",    help="Etykieta okna Klienta-1")

    # Klient 2
    g2 = p.add_argument_group("Klient 2")
    g2.add_argument("--host2",       default=None,           help="Host serwera dla Klienta-2 (domyślnie: jak --host1)")
    g2.add_argument("--port2",       default=None, type=int, help="Port serwera dla Klienta-2 (domyślnie: jak --port1)")
    g2.add_argument("--local-host2", default=None, dest="local_host2",
                    help="Lokalny interfejs sieciowy Klienta-2. "
                         "Domyślnie: system wybiera automatycznie.")
    g2.add_argument("--label2",      default="Klient-2",    help="Etykieta okna Klienta-2")

    # Wspólny host/port (nadpisywany przez host1/2 pod Windowsa)
    g0 = p.add_argument_group("Skrót (wspólny serwer dla obu klientów)")
    g0.add_argument("--host", default=DEFAULT_HOST, help="Domyślny host serwera (gdy --host1/--host2 pominięte)")
    g0.add_argument("--port", default=DEFAULT_PORT, type=int, help="Domyślny port serwera (gdy --port1/--port2 pominięte)")

    return p.parse_args()


def resolve(specific, fallback):
    return specific if specific is not None else fallback


def launch_client(main_path: str, host: str, port: int, label: str, local_host: str | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["STMP_HOST"]  = host
    env["STMP_PORT"]  = str(port)
    env["STMP_LABEL"] = label
    if local_host:
        env["STMP_LOCAL_HOST"] = local_host

    cmd = [sys.executable, main_path,
           "--host",  host,
           "--port",  str(port),
           "--label", label]
    if local_host:
        cmd += ["--local-host", local_host]

    proc = subprocess.Popen(cmd, env=env)
    local_info = f"  (bind: {local_host})" if local_host else ""
    print(f"[launcher] '{label}' → PID {proc.pid}  serwer: {host}:{port}{local_info}")
    return proc


def wait_for_processes(processes: list):
    print("\n[launcher] Obaj klienci działają. Naciśnij Ctrl+C, aby zamknąć wszystkie.\n")
    try:
        while True:
            if not any(p.poll() is None for p in processes):
                print("[launcher] Wszystkie procesy zakończyły działanie.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[launcher] Ctrl+C — zamykam wszystkie procesy…")
        for p in processes:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGTERM)
                except Exception:
                    pass
        time.sleep(1.0)
        for p in processes:
            if p.poll() is None:
                p.kill()
        print("[launcher] Zakończono.")


def main():
    args = parse_args()

    if not os.path.isfile(DEFAULT_MAIN):
        print(f"[błąd] Nie znaleziono main.py: {DEFAULT_MAIN}")
        sys.exit(1)

    host1       = resolve(args.host1, args.host)
    port1       = resolve(args.port1, args.port)
    host2       = resolve(args.host2, args.host)
    port2       = resolve(args.port2, args.port)
    local_host1 = args.local_host1
    local_host2 = args.local_host2

    print(f"[launcher] main.py  : {DEFAULT_MAIN}")
    print(f"[launcher] {args.label1}: serwer={host1}:{port1}" + (f"  bind={local_host1}" if local_host1 else ""))
    print(f"[launcher] {args.label2}: serwer={host2}:{port2}" + (f"  bind={local_host2}" if local_host2 else ""))

    if host1 == host2 and port1 == port2:
        print("[launcher] Obaj klienci łączą się z tym samym serwerem.")
    else:
        print("[launcher] Klienci łączą się z RÓŻNYMI serwerami.")
    if local_host1 or local_host2:
        print(f"[launcher] Klienci używają różnych interfejsów lokalnych "
              f"({local_host1 or 'auto'} / {local_host2 or 'auto'}) — "
              f"serwer będzie widział różne IP źródłowe.")
    print()

    processes = []
    processes.append(launch_client(DEFAULT_MAIN, host1, port1, args.label1, local_host1))
    time.sleep(DEFAULT_DELAY)
    processes.append(launch_client(DEFAULT_MAIN, host2, port2, args.label2, local_host2))

    wait_for_processes(processes)


if __name__ == "__main__":
    main()