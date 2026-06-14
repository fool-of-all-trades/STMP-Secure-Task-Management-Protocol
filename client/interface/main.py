import tkinter as tk
import asyncio
import threading
from tkinter import messagebox
import argparse
import os

from welcome import show_welcome_screen
from login import show_login_screen
from registration import show_registration_screen
from dashboard import show_dashboard_screen
from client.client import STMPClient

import logging


# Parsowanie argumentów i zmiennych środowiskowych
def parse_args():
    p = argparse.ArgumentParser(description="Klient STMP")
    p.add_argument("--host",       default=os.environ.get("STMP_HOST", "127.0.0.1"))
    p.add_argument("--port",       default=int(os.environ.get("STMP_PORT", "8888")), type=int)
    p.add_argument("--label",      default=os.environ.get("STMP_LABEL", "Klient"),
                   help="Etykieta wyświetlana w tytule okna i logach")
    p.add_argument("--local-host", default=os.environ.get("STMP_LOCAL_HOST", None),
                   dest="local_host",
                   help="Lokalny interfejs sieciowy do bindowania (np. 192.168.1.5). "
                        "Domyślnie: system wybiera automatycznie.")
    return p.parse_args()


# Kontroler GUI
class STMPGuiController:
    def __init__(self, root: tk.Tk, host: str, port: int, label: str, local_host: str | None = None):
        self.root  = root
        self.label = label
        self.client = STMPClient(host=host, port=port, local_host=local_host)
        self._host       = host
        self._port       = port
        self._local_host = local_host
        self.current_username = None

        # Osobna pętla asyncio dla wątku tła
        self.async_loop = asyncio.new_event_loop()
        self.network_thread = threading.Thread(
            target=self._run_async_loop, daemon=True, name=f"{label}-network"
        )
        self.network_thread.start()

    # Uruchomienie pętli asyncio w osobnym wątku
    def _run_async_loop(self):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_forever()

    def run_async(self, coroutine):
        return asyncio.run_coroutine_threadsafe(coroutine, self.async_loop)

    # Inicjalizacja połączenia
    def start_application(self):
        # Czekanie na wynik w GUI
        future = self.run_async(self.client.connect())

        def check_connection():
            try:
                # Pobranie wyniku (z timeoutem, żeby nie zamrozić GUI)
                connected = future.result(timeout=5.0)
                if connected:
                    self.navigate_to_welcome()
                else:
                    self._show_critical_error("Could not establish secure STMP connection to server.")
            except Exception as e:
                self._show_critical_error(f"Connection failure: {e}")

        # 100ms dla serwera na zestawienie TLS, zanim zostanie sprawdzony stan
        self.root.after(100, check_connection)

    def _show_critical_error(self, msg):
        messagebox.showerror("Critical Connection Error", msg)
        self.root.destroy()

    # Wystartowanie aplikacje w oknie Welcome
    def navigate_to_welcome(self):
        show_welcome_screen(self.root, on_get_started=self.navigate_to_login)

    # Przeniesienie użytkownika do logowania
    def navigate_to_login(self):
        show_login_screen(
            self.root,
            self,
            on_success=self.handle_authenticated_session,
            on_navigate_register=self.navigate_to_registration,
            on_back=self.navigate_to_welcome,
        )

    # Przenisienie użytkownika do rejestracji
    def navigate_to_registration(self):
        show_registration_screen(
            self.root,
            self,
            on_success=self.navigate_to_login,
            on_navigate_login=self.navigate_to_login,
            on_back=self.navigate_to_login,
        )

    # Przeniesienie użytkownika do dashboard po zalogowaniu
    def handle_authenticated_session(self, username):
        self.current_username = username
        show_dashboard_screen(
            self.root,
            self,
            username=self.current_username,
            on_logout=self.handle_logout,
        )

    def handle_logout(self):
        # Rozłączenie starego klienta w tle
        self.run_async(self.client.disconnect())

        self.client = STMPClient(host=self._host, port=self._port, local_host=self._local_host)
        future = self.run_async(self.client.connect())

        def on_reconnected():
            try:
                connected = future.result(timeout=5.0)
                if connected:
                    self.navigate_to_welcome()
                else:
                    self._show_critical_error("Could not reconnect after logout.")
            except Exception as e:
                self._show_critical_error(f"Reconnect failure: {e}")

        self.root.after(100, on_reconnected)


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG,
        format=f"%(asctime)s [{args.label}] [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = tk.Tk()
    root.title(f"STMP — {args.label}")   # Rozróżnienie okien na pasku zadań (dla 2 klientów)

    coordinator = STMPGuiController(root, host=args.host, port=args.port, label=args.label, local_host=args.local_host)
    coordinator.start_application()
    root.mainloop()


if __name__ == "__main__":
    main()