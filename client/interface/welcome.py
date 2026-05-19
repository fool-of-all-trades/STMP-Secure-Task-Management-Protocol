"""Welcome screen for STMP Secure Task Manager"""
import tkinter as tk
from tkinter import messagebox
from auth_utils import COLOR_PRIMARY, get_button_styles, prepare_screen

APP_NAME = "STMP Secure Task Manager"
DESCRIPTION = "Welcome to STMP – Secure Task Manager.\nA simple welcome screen for the application."
PROJECT_INFO = (
    "Project: STMP Secure Task Manager\n"
    "Model: Client-Server with STMP/1.0 protocol\n"
    "Technologies: Python + TLS + JSON + SQLite/DB"
)

def show_welcome_screen(root, on_get_started):
    prepare_screen(root, 500, 260, APP_NAME)

    title_label = tk.Label(root, text=APP_NAME, font=("Segoe UI", 18, "bold"), fg=COLOR_PRIMARY)
    title_label.pack(pady=(35, 12))

    description_label = tk.Label(root, text=DESCRIPTION, font=("Segoe UI", 11), justify="center", wraplength=450)
    description_label.pack(padx=20, pady=(0, 20))

    button_frame = tk.Frame(root)
    button_frame.pack(pady=(0, 30))
    btn_styles = get_button_styles()

    tk.Button(button_frame, text="Get Started", command=on_get_started, **btn_styles).grid(row=0, column=0, padx=8, ipady=4)
    tk.Button(button_frame, text="Info", command=lambda: messagebox.showinfo("App Information", PROJECT_INFO), **btn_styles).grid(row=0, column=1, padx=8, ipady=4)
    tk.Button(button_frame, text="Quit", command=root.destroy, **btn_styles).grid(row=0, column=2, padx=8, ipady=4)