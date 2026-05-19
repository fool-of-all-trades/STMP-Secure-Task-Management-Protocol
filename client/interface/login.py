"""Login screen for STMP Secure Task Manager"""
import tkinter as tk
from tkinter import messagebox
from auth_utils import validate_username, validate_password, COLOR_PRIMARY, COLOR_ERROR, get_button_styles, prepare_screen

def show_login_screen(root, on_success, on_navigate_register, on_back):
    prepare_screen(root, 450, 400, "STMP - Sign In")
    
    title_label = tk.Label(root, text="Sign In", font=("Segoe UI", 18, "bold"), fg=COLOR_PRIMARY)
    title_label.pack(pady=(30, 20))
    
    tk.Label(root, text="Username:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5), fill="x")
    username_entry = tk.Entry(root, font=("Segoe UI", 10), width=30)
    username_entry.pack(padx=40, pady=(0, 15), fill="x", ipady=5)
    username_entry.focus()
    
    tk.Label(root, text="Password:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5), fill="x")
    password_entry = tk.Entry(root, font=("Segoe UI", 10), width=30, show="*")
    password_entry.pack(padx=40, pady=(0, 20), fill="x", ipady=5)
    
    error_label = tk.Label(root, text="", font=("Segoe UI", 9), fg=COLOR_ERROR)
    error_label.pack(pady=(0, 10))
    
    def handle_login():
        username = username_entry.get().strip()
        password = password_entry.get()
        
        if not username or not password:
            error_label.config(text="Please fill in all fields!")
            return
            
        is_valid, msg = validate_username(username)
        if not is_valid:
            error_label.config(text=msg)
            return
            
        is_valid, msg = validate_password(password)
        if not is_valid:
            error_label.config(text=msg)
            return
            
        messagebox.showinfo("Success", f"Logged in successfully as: {username}")
        on_success(username)
        
    button_frame = tk.Frame(root)
    button_frame.pack(pady=20)
    btn_styles = get_button_styles()
    
    tk.Button(button_frame, text="Login", command=handle_login, **btn_styles).grid(row=0, column=0, padx=5, ipady=4)
    tk.Button(button_frame, text="Back", command=on_back, **btn_styles).grid(row=0, column=1, padx=5, ipady=4)
    
    register_frame = tk.Frame(root)
    register_frame.pack(pady=(10, 0))
    tk.Label(register_frame, text="Don't have an account? ", font=("Segoe UI", 9)).pack(side="left")
    
    register_link = tk.Label(register_frame, text="Sign up now", font=("Segoe UI", 9, "underline"), fg="blue", cursor="hand2")
    register_link.pack(side="left")
    register_link.bind("<Button-1>", lambda e: on_navigate_register())