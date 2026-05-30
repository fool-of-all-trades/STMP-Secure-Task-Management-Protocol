import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from auth_utils import create_auth_base_form, run_common_validation

root_path = Path(__file__).resolve().parents[2]
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from server.services.auth_service import register_user

# Ekran rejestracji
def show_registration_screen(root, on_success, on_navigate_login, on_back):
    # Walidacja danych rejestracji
    def handle_register():
        username = username_entry.get().strip()
        password = password_entry.get()
        confirm_password = confirm_password_entry.get()

        if not run_common_validation(username, password, message_label):
            return

        if not confirm_password:
            message_label.config(text="Please fill in all fields!")
            return

        if password != confirm_password:
            message_label.config(text="Passwords do not match!")
            return

        try:
            result = register_user(username, password, "127.0.0.1")
        except Exception:
            message_label.config(text="Unable to register user. Please check the database connection.")
            return

        if not result.get("ok"):
            message_label.config(text=result.get("message", "Registration failed."))
            return

        messagebox.showinfo("Success",
                            result.get("message", f"Registration for user '{username}' completed successfully!"))
        on_success()

    # Budowanie formularza rejestracji
    username_entry, password_entry, message_label, extra_fields_frame = create_auth_base_form(
        root=root, width=450, height=450,
        window_title="STMP - Create Account", form_title="Create Account",
        main_btn_text="Register", on_main_action=handle_register, on_back=on_back,
        nav_text="Already have an account? ", nav_link_text="Sign in here", on_nav_click=on_navigate_login
    )

    tk.Label(extra_fields_frame, text="Confirm Password:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5),
                                                                                                   fill="x")
    confirm_password_entry = tk.Entry(extra_fields_frame, font=("Segoe UI", 10), width=30, show="*")
    confirm_password_entry.pack(padx=40, pady=(0, 5), fill="x", ipady=5)