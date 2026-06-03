import tkinter as tk
from tkinter import messagebox, ttk
from auth_utils import COLOR_PRIMARY, COLOR_ERROR, get_button_styles

# Ekran dodawania nowych zadań do listy
def show_add_task_dialog(root, coordinator, on_task_created):
    dialog = tk.Toplevel(root)
    dialog.title("STMP - Add New Task")
    dialog.transient(root)
    dialog.grab_set()

    # Centrowanie okna dialogowego względem okna głównego
    width, height = 400, 380
    x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.resizable(False, False)

    # Nagłówek okna
    title_label = tk.Label(dialog, text="Create New Task", font=("Segoe UI", 14, "bold"), fg=COLOR_PRIMARY)
    title_label.pack(pady=(15, 10))

    # Tytuł zadania
    tk.Label(dialog, text="Task Title *:", font=("Segoe UI", 10), anchor="w").pack(padx=25, pady=(5, 2), fill="x")
    title_entry = tk.Entry(dialog, font=("Segoe UI", 10))
    title_entry.pack(padx=25, pady=(0, 10), fill="x", ipady=3)
    title_entry.focus()

    # Opis zadania
    tk.Label(dialog, text="Description:", font=("Segoe UI", 10), anchor="w").pack(padx=25, pady=(5, 2), fill="x")
    desc_text = tk.Text(dialog, font=("Segoe UI", 10), height=4)
    desc_text.pack(padx=25, pady=(0, 10), fill="x")

    # Status zadania
    tk.Label(dialog, text="Initial Status:", font=("Segoe UI", 10), anchor="w").pack(padx=25, pady=(5, 2), fill="x")
    status_combobox = ttk.Combobox(dialog, values=["todo", "done"], state="readonly", font=("Segoe UI", 10))
    status_combobox.set("todo")
    status_combobox.pack(padx=25, pady=(0, 15), fill="x")

    # Etykieta komunikatów o błędach
    error_label = tk.Label(dialog, text="", font=("Segoe UI", 9), fg=COLOR_ERROR, wraplength=350)
    error_label.pack()

    def handle_submit():
        title = title_entry.get().strip()
        description = desc_text.get("1.0", "end").strip()
        status = status_combobox.get()

        if not title:
            error_label.config(text="Task title is required!")
            return

        # Wywołanie dodawania zadania przez clienta
        future = coordinator.run_async(
            coordinator.client.create_task(title, description, status)
        )

        try:
            response = future.result(timeout=5.0)

            if response.get("type") == "TASK_CREATED":
                messagebox.showinfo("Success", "Task created successfully!", parent=dialog)
                dialog.destroy()
                on_task_created()  # Wywołanie odświeżenia tabeli w dashboardzie
            else:
                payload = response.get("payload", {})
                error_label.config(text=payload.get("message", "Failed to create task."))
        except Exception as e:
            error_label.config(text=f"Network error: {str(e)}")

    # Sekcja przycisków akcji
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=15, side="bottom")
    btn_styles = get_button_styles()

    tk.Button(button_frame, text="Save Task", command=handle_submit, **btn_styles).grid(row=0, column=0, padx=5, ipady=2)

    btn_styles_cancel = btn_styles.copy()
    btn_styles_cancel.update({"bg": "#7f8c8d", "activebackground": "#95a5a6"})
    tk.Button(button_frame, text="Cancel", command=dialog.destroy, **btn_styles_cancel).grid(row=0, column=1, padx=5, ipady=2)