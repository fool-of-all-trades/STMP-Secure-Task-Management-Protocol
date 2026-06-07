from tkinter import messagebox
from auth_utils import create_auth_base_form
from client.actions.auth_actions import perform_login

# Ekran logowania
def show_login_screen(root, coordinator, on_success, on_navigate_register, on_back):
    def handle_login():
        username = username_entry.get().strip()
        password = password_entry.get()

        result = perform_login(coordinator, username, password)

        if result["success"]:
            messagebox.showinfo("Success", f"Logged in successfully as: {username}")
            on_success(username)
        else:
            message_label.config(text=result["message"])

    # Budowanie formularza logowania
    username_entry, password_entry, message_label, _ = create_auth_base_form(
        root=root, width=450, height=400,
        window_title="STMP - Sign In", form_title="Sign In",
        main_btn_text="Login", on_main_action=handle_login, on_back=on_back,
        nav_text="Don't have an account? ", nav_link_text="Sign up now", on_nav_click=on_navigate_register
    )