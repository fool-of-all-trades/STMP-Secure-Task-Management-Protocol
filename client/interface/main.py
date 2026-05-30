import tkinter as tk
from welcome import show_welcome_screen
from login import show_login_screen
from registration import show_registration_screen
from dashboard import show_dashboard_screen

class STMPGuiController:
    def __init__(self, root):
        self.root = root
        self.current_username = None

    # Wystartowanie aplikacje w oknie Welcome
    def navigate_to_welcome(self):
        show_welcome_screen(
            self.root,
            on_get_started=self.navigate_to_login
        )

    # Przeniesienie użytkownika do logowania
    def navigate_to_login(self):
        show_login_screen(
            self.root,
            on_success=self.handle_authenticated_session,
            on_navigate_register=self.navigate_to_registration,
            on_back=self.navigate_to_welcome
        )

    # Przenisienie użytkownika do rejestracji
    def navigate_to_registration(self):
        show_registration_screen(
            self.root,
            on_success=self.navigate_to_login,
            on_navigate_login=self.navigate_to_login,
            on_back=self.navigate_to_login
        )

    #Przeniesienie użytkownika do dashboard po zalogowaniu
    def handle_authenticated_session(self, username):
        self.current_username = username

        show_dashboard_screen(
            self.root,
            username=self.current_username,
            on_logout=self.navigate_to_welcome
        )

def main():
    root = tk.Tk()
    coordinator = STMPGuiController(root)
    coordinator.navigate_to_welcome()
    root.mainloop()

if __name__ == "__main__":
    main()