import tkinter as tk
import asyncio
import threading
from tkinter import messagebox

from welcome import show_welcome_screen
from login import show_login_screen
from registration import show_registration_screen
from dashboard import show_dashboard_screen
from client.client import STMPClient

class STMPGuiController:
    def __init__(self, root):
        self.root = root
        self.client = STMPClient(host="127.0.0.1", port=8888)
        self.current_username = None

        # Osobna pętlaa asyncio dla wątku tła
        self.async_loop = asyncio.new_event_loop()
        self.network_thread = threading.Thread(target=self._run_async_loop, daemon=True)
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
            self,  # Przekazujemy kontroler (żeby ekrany mogły używać run_async)
            on_success=self.handle_authenticated_session,
            on_navigate_register=self.navigate_to_registration,
            on_back=self.navigate_to_welcome
        )

    # Przenisienie użytkownika do rejestracji
    def navigate_to_registration(self):
        show_registration_screen(
            self.root,
            self,  # Przekazujemy kontroler
            on_success=self.navigate_to_login,
            on_navigate_login=self.navigate_to_login,
            on_back=self.navigate_to_login
        )

    # Przeniesienie użytkownika do dashboard po zalogowaniu
    def handle_authenticated_session(self, username):
        self.current_username = username
        show_dashboard_screen(
            self.root,
            self,  # Przekazujemy kontroler
            username=self.current_username,
            on_logout=self.handle_logout
        )

    def handle_logout(self):
        # Bezpieczne rozłączenie w tle
        self.run_async(self.client.disconnect())
        self.navigate_to_welcome()


def main():
    root = tk.Tk()
    coordinator = STMPGuiController(root)
    coordinator.start_application()
    root.mainloop()


if __name__ == "__main__":
    main()