import tkinter as tk
from tkinter import messagebox
from auth_utils import create_auth_base_form, run_common_validation

# Ekran rejestracji
def show_registration_screen(root, coordinator, on_success, on_navigate_login, on_back):
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

        # GUI -> STMP Client -> TLS -> Server
        future = coordinator.run_async(
            coordinator.client.request("REGISTER", {"username": username, "password": password})
        )

        try:
            response = future.result(timeout=5.0)

            if response.get("type") == "REGISTER_OK":
                messagebox.showinfo("Success", f"Registration for user '{username}' completed successfully!")
                on_success()
            else:
                payload = response.get("payload", {})
                message_label.config(text=payload.get("message", "Registration failed."))
        except Exception as e:
            message_label.config(text=f"Network error: {str(e)}")

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