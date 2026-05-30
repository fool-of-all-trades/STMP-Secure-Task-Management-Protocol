import tkinter as tk
from tkinter import messagebox, ttk
from auth_utils import COLOR_PRIMARY, get_button_styles, prepare_screen

# Ekran główny po zalogowaniu
def show_dashboard_screen(root, username, on_logout):
    prepare_screen(root, 600, 500, f"STMP - Dashboard ({username})")

    # Górny pasek
    header_frame = tk.Frame(root, bg=COLOR_PRIMARY, height=50)
    header_frame.pack(fill="x", side="top")
    header_frame.pack_propagate(False)

    # Informacje o zalogowanym użytkowniku
    user_label = tk.Label(
        header_frame,
        text=f"Logged in as: {username}",
        font=("Segoe UI", 11, "bold"),
        fg="white",
        bg=COLOR_PRIMARY
    )
    user_label.pack(side="left", padx=15, pady=10)

    # Przycisk wylogowania
    btn_styles = get_button_styles()
    btn_styles_logout = btn_styles.copy()
    btn_styles_logout.update({"bg": "#d32f2f", "activebackground": "#b71c1c", "width": 10})

    def handle_logout():
        if messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            on_logout()

    logout_button = tk.Button(header_frame, text="Logout", command=handle_logout, **btn_styles_logout)
    logout_button.pack(side="right", padx=15, pady=8)

    # Główny obszar roboczy
    content_frame = tk.Frame(root)
    content_frame.pack(fill="both", expand=True, padx=20, pady=20)

    title_label = tk.Label(content_frame, text="Your Tasks", font=("Segoe UI", 14, "bold"),
                           fg=COLOR_PRIMARY)
    title_label.pack(anchor="w", pady=(0, 10))

    # Tabela zadań
    columns = ("id", "title", "status")
    tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=12)
    tree.heading("id", text="ID")
    tree.heading("title", text="Title")
    tree.heading("status", text="Status")

    tree.column("id", width=50, anchor="center")
    tree.column("title", width=350, anchor="w")
    tree.column("status", width=100, anchor="center")

    tree.pack(fill="both", expand=True, pady=5)

    # TODO: Integracja z server.services.task_service.list_tasks(session_token)
    # Zamiast tych przykładów
    tree.insert("", "end", values=("1", "Przykład 1", "todo"))
    tree.insert("", "end", values=("2", "Przykład 2", "done"))

    # Dolny pasek akcji dla zadań
    actions_frame = tk.Frame(content_frame)
    actions_frame.pack(fill="x", pady=10)

    def add_task_stub():
        messagebox.showinfo("Action", "The window for adding a new task will open here.")

    tk.Button(actions_frame, text="Add a task", command=add_task_stub, **btn_styles).pack(side="left", padx=5)