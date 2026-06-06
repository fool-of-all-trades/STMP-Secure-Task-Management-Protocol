import tkinter as tk
from tkinter import messagebox, ttk
from auth_utils import COLOR_PRIMARY, get_button_styles, prepare_screen
from task_dialog import show_task_dialog
from datetime import datetime, timezone


def show_dashboard_screen(root, coordinator, username, on_logout):
    prepare_screen(root, 750, 530, f"STMP - Dashboard ({username})")

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

    columns = ("id", "title", "description", "status")
    tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=12)
    tree.heading("id", text="ID")
    tree.heading("title", text="Title")
    tree.heading("description", text="Description")
    tree.heading("status", text="Status")

    tree.column("id", width=60, anchor="center")
    tree.column("title", width=220, anchor="w")
    tree.column("description", width=310, anchor="w")
    tree.column("status", width=100, anchor="center")
    tree.pack(fill="both", expand=True, pady=5)

    # Pobranie zadań z serwera przez protokół sieciowy
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
                    clean_desc = task.get("description", "").replace("\n", " ")
                    tree.insert("", "end", values=(t_id, task.get("title"), clean_desc, task.get("status")))
            elif response.get("type") == "ERROR":
                messagebox.showerror("Error", response.get("payload", {}).get("message", "Failed to fetch tasks."))
        except Exception as e:
            tree.insert("", "end", values=("!", "No tasks fetched from server yet", "", "mock"))

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
                task_data=task_data
            )
        else:
            messagebox.showerror("Error", "Task data context unavailable.")

    def handle_delete_task():
        selected_item = tree.selection()
        if not selected_item:
            messagebox.showwarning("Selection Required", "Please select a task from the list to delete.")
            return

        # Pobranie ID zaznaczonego wiersza
        values = tree.item(selected_item[0], "values")
        task_id = str(values[0])
        task_title = str(values[1])

        # Wyświetlenie okna z potwierdzeniem
        if messagebox.askyesno("Confirm Deletion",
                               f"Are you sure you want to permanently delete task:\n'{task_title}'?"):
            future = coordinator.run_async(coordinator.client.delete_task(task_id))

            try:
                # Odbiór komunikatu z klienta
                result = future.result(timeout=5.0)
                if result["success"]:
                    messagebox.showinfo("Success", result["message"])
                    fetch_tasks_from_server()
                else:
                    messagebox.showerror("Error", result["message"])
            except Exception as e:
                messagebox.showerror("Error", f"Application error: {str(e)}")

    # Przycisk "dodaj"
    tk.Button(actions_frame, text="Add a task", command=open_add_task_window, **btn_styles).pack(side="left", padx=5)

    # Przycisk "edytuj"
    btn_styles_edit = btn_styles.copy()
    btn_styles_edit.update({"bg": "#f39c12", "activebackground": "#e67e22"})
    tk.Button(actions_frame, text="Edit selected", command=open_edit_task_window, **btn_styles_edit).pack(side="left", padx=5)

    btn_styles_delete = btn_styles.copy()
    btn_styles_delete.update({"bg": "#d32f2f", "activebackground": "#b71c1c"})
    tk.Button(actions_frame, text="Delete selected", command=handle_delete_task, **btn_styles_delete).pack(side="left", padx=5)

    # Pasek statusu sesji
    STATUS_COLORS = {
        "SESSION_ACTIVE":   ("#e8f5e9", "#2e7d32"),
        "CONNECTED":        ("#e3f2fd", "#1565c0"),
        "WAITING_FOR_AUTH": ("#fff8e1", "#f57f17"),
        "DISCONNECTED":     ("#ffebee", "#c62828"),
        "SESSION_EXPIRED":  ("#fce4ec", "#880e4f"),
    }
    STATUS_LABELS = {
        "SESSION_ACTIVE":   "● Session active",
        "CONNECTED":        "● Connected — not authenticated",
        "WAITING_FOR_AUTH": "● Waiting for authentication...",
        "DISCONNECTED":     "● Disconnected",
        "SESSION_EXPIRED":  "● Session expired — please log in again",
    }

    status_bar = tk.Frame(root, height=28)
    status_bar.pack(fill="x", side="bottom")
    status_bar.pack_propagate(False)

    status_dot = tk.Label(status_bar, font=("Segoe UI", 9), padx=10, anchor="w")
    status_dot.pack(side="left", fill="both", expand=True)

    expires_label = tk.Label(status_bar, font=("Segoe UI", 9), padx=10, anchor="e", fg="#555")
    expires_label.pack(side="right")

    # Zmienna do zatrzymania pętli odświeżania po wyjściu z dashboardu
    _active = [True]

    def refresh_status_bar():
        if not _active[0]:
            return

        state = coordinator.client.session.state
        bg, fg = STATUS_COLORS.get(state, ("#f5f5f5", "#333333"))
        text   = STATUS_LABELS.get(state, f"● {state}")

        status_bar.config(bg=bg)
        status_dot.config(text=text, bg=bg, fg=fg)

        exp = coordinator.client.session.expires_at
        if exp:
            remaining = exp - datetime.now(timezone.utc)
            total_sec = int(remaining.total_seconds())
            if total_sec > 0:
                mins, secs = divmod(total_sec, 60)
                expires_label.config(text=f"Token expires in: {mins}m {secs:02d}s", bg=bg, fg="#555")
            else:
                expires_label.config(text="Token expired", bg=bg, fg="#c62828")
        else:
            expires_label.config(text="", bg=bg)

        root.after(1000, refresh_status_bar)

    # Zatrzymanie odświeżania przy wyjściu z dashboardu (np. logout)
    original_on_logout = on_logout
    def on_logout_with_cleanup():
        _active[0] = False
        original_on_logout()

    logout_button.config(command=lambda: messagebox.askyesno("Logout", "Are you sure you want to log out?") and on_logout_with_cleanup())

    fetch_tasks_from_server()
    refresh_status_bar()