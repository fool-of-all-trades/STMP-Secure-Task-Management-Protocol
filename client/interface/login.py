import sys
from pathlib import Path
from tkinter import messagebox
from auth_utils import create_auth_base_form, run_common_validation

root_path = Path(__file__).resolve().parents[2]
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from server.services.auth_service import login_user

# Ekran logowania
def show_login_screen(root, on_success, on_navigate_register, on_back):
    # Walidacja danych logowania
    def handle_login():
        username = username_entry.get().strip()
        password = password_entry.get()

        if not run_common_validation(username, password, message_label):
            return

        try:
            result = login_user(username, password, "127.0.0.1")
        except Exception:
            message_label.config(text="Unable to login. Please check the database connection.")
            return

        if not result.get("ok"):
            message_label.config(text=result.get("message", "Login failed."))
            return

        messagebox.showinfo("Success", result.get("message", f"Logged in successfully as: {username}"))
        on_success(username)

    # Budowanie formularza logowania
    username_entry, password_entry, message_label, _ = create_auth_base_form(
        root=root, width=450, height=400,
        window_title="STMP - Sign In", form_title="Sign In",
        main_btn_text="Login", on_main_action=handle_login, on_back=on_back,
        nav_text="Don't have an account? ", nav_link_text="Sign up now", on_nav_click=on_navigate_register
    )