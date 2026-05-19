"""Application view coordinator and main engine runner"""
import tkinter as tk
from welcome import show_welcome_screen
from login import show_login_screen
from registration import show_registration_screen

class STMPGuiController:
    def __init__(self, root):
        self.root = root
        
    def navigate_to_welcome(self):
        show_welcome_screen(
            self.root, 
            on_get_started=self.navigate_to_login
        )
        
    def navigate_to_login(self):
        show_login_screen(
            self.root,
            on_success=self.handle_authenticated_session,
            on_navigate_register=self.navigate_to_registration,
            on_back=self.navigate_to_welcome
        )
        
    def navigate_to_registration(self):
        show_registration_screen(
            self.root,
            on_success=self.navigate_to_login,
            on_navigate_login=self.navigate_to_login,
            on_back=self.navigate_to_login
        )
        
    def handle_authenticated_session(self, username):
        """Dispatches user straight into the dashboard workspace view layer"""
        print(f"User {username} authenticated. Moving into task overview space...")
        # TODO: view of the user list only after logging in


def main():
    root = tk.Tk()
    coordinator = STMPGuiController(root)
    coordinator.navigate_to_welcome()
    root.mainloop()


if __name__ == "__main__":
    main()