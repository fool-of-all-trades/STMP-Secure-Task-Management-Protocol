import tkinter as tk
from tkinter import messagebox
from auth_utils import COLOR_PRIMARY, get_button_styles
from client.actions.auth_actions import perform_reauth

# Okno ponownego logowania
def show_reauth_dialog(root, coordinator, username, on_success, on_logout):
    dialog = tk.Toplevel(root)
    dialog.title("Session lost — re-authenticate")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.protocol("WM_DELETE_WINDOW", lambda: None)  # Zakaz zamknięcia przez X

    # Wyśrodkowanie dialogu nad głównym oknem
    root.update_idletasks()
    rx, ry = root.winfo_x(), root.winfo_y()
    rw, rh = root.winfo_width(), root.winfo_height()
    dw, dh = 360, 260
    dialog.geometry(f"{dw}x{dh}+{rx + (rw - dw) // 2}+{ry + (rh - dh) // 2}")

    # Nagłówek
    header = tk.Frame(dialog, bg=COLOR_PRIMARY, height=46)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(
        header, text="Session disconnected",
        font=("Segoe UI", 11, "bold"), fg="white", bg=COLOR_PRIMARY
    ).pack(side="left", padx=15, pady=10)

    # Treść
    body = tk.Frame(dialog, padx=24, pady=16)
    body.pack(fill="both", expand=True)

    tk.Label(
        body,
        text=f"Connection was lost. Re-enter your\npassword to continue as  {username}.",
        font=("Segoe UI", 10), justify="left", anchor="w"
    ).pack(anchor="w", pady=(0, 14))

    tk.Label(body, text="Password", font=("Segoe UI", 9, "bold"), anchor="w").pack(anchor="w")
    password_entry = tk.Entry(body, show="●", font=("Segoe UI", 11), relief="solid", bd=1)
    password_entry.pack(fill="x", ipady=5, pady=(3, 0))
    password_entry.focus_set()

    message_label = tk.Label(body, text="", font=("Segoe UI", 9), fg="#c62828", anchor="w")
    message_label.pack(anchor="w", pady=(4, 0))

    # Przyciski
    btn_frame = tk.Frame(body)
    btn_frame.pack(fill="x", pady=(12, 0))
    btn_styles = get_button_styles()

    def handle_relogin():
        message_label.config(text="Connecting...")
        dialog.update_idletasks()

        result = perform_reauth(coordinator, username, password_entry.get())

        if result["success"]:
            dialog.grab_release()
            dialog.destroy()
            on_success()
        else:
            message_label.config(text=result["message"])

    def handle_logout():
        if messagebox.askyesno("Logout", "Give up and log out?", parent=dialog):
            dialog.grab_release()
            dialog.destroy()
            on_logout()

    tk.Button(
        btn_frame, text="Reconnect", command=handle_relogin,
        **{**btn_styles, "width": 12}
    ).pack(side="left")

    btn_logout_styles = {**btn_styles, "bg": "#d32f2f", "activebackground": "#b71c1c", "width": 10}
    tk.Button(
        btn_frame, text="Logout", command=handle_logout,
        **btn_logout_styles
    ).pack(side="right")

    password_entry.bind("<Return>", lambda _: handle_relogin())