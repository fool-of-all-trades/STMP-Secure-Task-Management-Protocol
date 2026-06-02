from tkinter import messagebox
from auth_utils import create_auth_base_form, run_common_validation

# Ekran logowania
def show_login_screen(root, coordinator, on_success, on_navigate_register, on_back):
    def handle_login():
        username = username_entry.get().strip()
        password = password_entry.get()

        if not run_common_validation(username, password, message_label):
            return

        # GUI -> STMP Client -> TLS -> Server
        future = coordinator.run_async(
            coordinator.client.request("LOGIN", {"username": username, "password": password})
        )

        try:
            # Max 5 sekund na odpowiedź, bez blokowania pętli asyncio tła
            response = future.result(timeout=5.0)

            if response.get("type") == "LOGIN_OK":
                messagebox.showinfo("Success", f"Logged in successfully as: {username}")
                on_success(username)
            else:
                payload = response.get("payload", {})
                message_label.config(text=payload.get("message", "Login failed."))
        except Exception as e:
            message_label.config(text=f"Network error: {str(e)}")

    # Budowanie formularza logowania
    username_entry, password_entry, message_label, _ = create_auth_base_form(
        root=root, width=450, height=400,
        window_title="STMP - Sign In", form_title="Sign In",
        main_btn_text="Login", on_main_action=handle_login, on_back=on_back,
        nav_text="Don't have an account? ", nav_link_text="Sign up now", on_nav_click=on_navigate_register
    )