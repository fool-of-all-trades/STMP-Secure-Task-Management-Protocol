import tkinter as tk
from tkinter import messagebox
from auth_utils import create_auth_base_form
from client.actions.auth_actions import perform_register

# Ekran rejestracji
def show_registration_screen(root, coordinator, on_success, on_navigate_login, on_back):
    def handle_register():
        username = username_entry.get().strip()
        password = password_entry.get()
        confirm_password = confirm_password_entry.get()

        result = perform_register(coordinator, username, password, confirm_password)

        if result["success"]:
            messagebox.showinfo("Success", f"Registration for user '{username}' completed successfully!")
            on_success()
        else:
            message_label.config(text=result["message"])

    # Budowanie formularza rejestracji
    username_entry, password_entry, message_label, extra_fields_frame = create_auth_base_form(
        root=root, width=450, height=450,
        window_title="STMP - Create Account", form_title="Create Account",
        main_btn_text="Register", on_main_action=handle_register, on_back=on_back,
        nav_text="Already have an account? ", nav_link_text="Sign in here", on_nav_click=on_navigate_login
    )

    tk.Label(extra_fields_frame, text="Confirm Password:", font=("Segoe UI", 10), anchor="w").pack(
        padx=40, pady=(0, 5), fill="x"
    )
    confirm_password_entry = tk.Entry(extra_fields_frame, font=("Segoe UI", 10), width=30, show="*")
    confirm_password_entry.pack(padx=40, pady=(0, 5), fill="x", ipady=5)