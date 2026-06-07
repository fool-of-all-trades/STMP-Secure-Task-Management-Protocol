import tkinter as tk
from tkinter import messagebox, ttk
from auth_utils import COLOR_PRIMARY, COLOR_ERROR, get_button_styles
from client.actions.task_actions import create_task, update_task

# Ogólne okno do CRUD zadań
def show_task_dialog(root, coordinator, on_success, task_data=None):
    is_edit_mode = task_data is not None
    dialog = tk.Toplevel(root)
    dialog.transient(root)
    dialog.grab_set()

    window_title = "STMP - Edit Task" if is_edit_mode else "STMP - Add New Task"
    form_title = "Modify Existing Task" if is_edit_mode else "Create New Task"
    submit_btn_text = "Update Task" if is_edit_mode else "Save Task"

    dialog.title(window_title)

    # Centrowanie okna
    width, height = 400, 380
    x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
    y = root.winfo_y() + (root.winfo_height() // 2) - (height // 2)
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.resizable(False, False)

    # Nagłówek okna
    tk.Label(dialog, text=form_title, font=("Segoe UI", 14, "bold"), fg=COLOR_PRIMARY).pack(pady=(15, 10))

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
    tk.Label(dialog, text="Status:", font=("Segoe UI", 10), anchor="w").pack(padx=25, pady=(5, 2), fill="x")
    status_combobox = ttk.Combobox(dialog, values=["todo", "done"], state="readonly", font=("Segoe UI", 10))
    status_combobox.set("todo")
    status_combobox.pack(padx=25, pady=(0, 15), fill="x")

    # Etykieta komunikatów o błędach
    error_label = tk.Label(dialog, text="", font=("Segoe UI", 9), fg=COLOR_ERROR, wraplength=350)
    error_label.pack()

    # Wypełnianie pól danymi (dla edycji)
    if is_edit_mode:
        title_entry.insert(0, task_data.get("title", ""))
        desc_text.insert("1.0", task_data.get("description", ""))
        status_combobox.set(task_data.get("status", "todo"))

    def handle_submit():
        title = title_entry.get().strip()
        description = desc_text.get("1.0", "end").strip()
        status = status_combobox.get()

        if is_edit_mode:
            result = update_task(coordinator, task_data.get("id"), title, description, status)
        else:
            result = create_task(coordinator, title, description, status)

        if result["success"]:
            messagebox.showinfo("Success", result["message"], parent=dialog)
            dialog.destroy()
            on_success()
        else:
            error_label.config(text=result["message"])

    # Przyciski
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=15, side="bottom")
    btn_styles = get_button_styles()

    tk.Button(button_frame, text=submit_btn_text, command=handle_submit, **btn_styles).grid(
        row=0, column=0, padx=5, ipady=2
    )

    btn_styles_cancel = btn_styles.copy()
    btn_styles_cancel.update({"bg": "#7f8c8d", "activebackground": "#95a5a6"})
    tk.Button(button_frame, text="Cancel", command=dialog.destroy, **btn_styles_cancel).grid(
        row=0, column=1, padx=5, ipady=2
    )