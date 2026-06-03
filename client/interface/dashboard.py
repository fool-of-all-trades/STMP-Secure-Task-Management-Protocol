import tkinter as tk
from tkinter import messagebox, ttk
from auth_utils import COLOR_PRIMARY, get_button_styles, prepare_screen
from task_dialog import show_task_dialog


def show_dashboard_screen(root, coordinator, username, on_logout):
    prepare_screen(root, 600, 500, f"STMP - Dashboard ({username})")

    # Górny pasek
    header_frame = tk.Frame(root, bg=COLOR_PRIMARY, height=50)
    header_frame.pack(fill="x", side="top")
    header_frame.pack_propagate(False)

    user_label = tk.Label(
        header_frame, text=f"Logged in as: {username}",
        font=("Segoe UI", 11, "bold"), fg="white", bg=COLOR_PRIMARY
    )
    user_label.pack(side="left", padx=15, pady=10)

    btn_styles = get_button_styles()
    btn_styles_logout = btn_styles.copy()
    btn_styles_logout.update({"bg": "#d32f2f", "activebackground": "#b71c1c", "width": 10})

    def handle_logout():
        if messagebox.askyesno("Logout", "Are you sure you want to log out?"):
            on_logout()

    logout_button = tk.Button(header_frame, text="Logout", command=handle_logout, **btn_styles_logout)
    logout_button.pack(side="right", padx=15, pady=8)

    content_frame = tk.Frame(root)
    content_frame.pack(fill="both", expand=True, padx=20, pady=20)

    title_label = tk.Label(content_frame, text="Your Tasks", font=("Segoe UI", 14, "bold"), fg=COLOR_PRIMARY)
    title_label.pack(anchor="w", pady=(0, 10))

    # Tabela zadań
    cached_tasks = {}

    columns = ("id", "title", "status")
    tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=12)
    tree.heading("id", text="ID")
    tree.heading("title", text="Title")
    tree.heading("status", text="Status")

    tree.column("id", width=80, anchor="center")
    tree.column("title", width=320, anchor="w")
    tree.column("status", width=100, anchor="center")
    tree.pack(fill="both", expand=True, pady=5)

    # Pobranie zadania z serwera przez protokół sieciowy
    def fetch_tasks_from_server():
        for item in tree.get_children():
            tree.delete(item)
        cached_tasks.clear()

        future = coordinator.run_async(coordinator.client.request("GET_TASK", {}))
        try:
            response = future.result(timeout=5.0)
            if response.get("type") == "TASK_LIST":
                tasks = response.get("payload", {}).get("tasks", [])
                for task in tasks:
                    t_id = task.get("id")
                    # Zapisanie całego zadanie (razem z opisem),aby je edytować bez ponownego odpytywania sieci
                    cached_tasks[str(t_id)] = task
                    tree.insert("", "end", values=(t_id, task.get("title"), task.get("status")))
            elif response.get("type") == "ERROR":
                messagebox.showerror("Error", response.get("payload", {}).get("message", "Failed to fetch tasks."))
        except Exception as e:
            tree.insert("", "end", values=("!", "No tasks fetched from server yet", "mock"))

    actions_frame = tk.Frame(content_frame)
    actions_frame.pack(fill="x", pady=10)

    # Wywołanie okna tworzenia nowego zadania
    def open_add_task_window():
        show_task_dialog(
            root=root,
            coordinator=coordinator,
            on_success=fetch_tasks_from_server
        )

    # Wywołanie okna edycja zadania (wywołanie ze sparsowanymi danymi z cache)
    def open_edit_task_window():
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showwarning("Selection Required", "Please select a task from the list to edit.")
            return

        # Pobranie ID zaznaczonego wiersza
        values = tree.item(selected_item[0], "values")
        task_id = str(values[0])

        task_data = cached_tasks.get(task_id)
        if task_data:
            show_task_dialog(
                root=root,
                coordinator=coordinator,
                on_success=fetch_tasks_from_server,
                task_data=task_data  # Przekazanie danych przełącza formularz w tryb EDYCJI
            )
        else:
            messagebox.showerror("Error", "Task data context unavailable.")

    tk.Button(actions_frame, text="Add a task", command=open_add_task_window, **btn_styles).pack(side="left", padx=5)

    btn_styles_edit = btn_styles.copy()
    btn_styles_edit.update({"bg": "#f39c12", "activebackground": "#e67e22"})  # pomarańczowy kolor przycisku edycji
    tk.Button(actions_frame, text="Edit selected", command=open_edit_task_window, **btn_styles_edit).pack(side="left",
                                                                                                          padx=5)

    fetch_tasks_from_server()