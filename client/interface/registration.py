"""Registration screen for STMP Secure Task Manager"""
import tkinter as tk
from tkinter import messagebox
from auth_utils import validate_username, validate_password, COLOR_PRIMARY, COLOR_ERROR, get_button_styles, prepare_screen

def show_registration_screen(root, on_success, on_navigate_login, on_back):
    prepare_screen(root, 450, 450, "STMP - Create Account")
    
    title_label = tk.Label(root, text="Create Account", font=("Segoe UI", 18, "bold"), fg=COLOR_PRIMARY)
    title_label.pack(pady=(20, 15))
    
    tk.Label(root, text="Username:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5), fill="x")
    username_entry = tk.Entry(root, font=("Segoe UI", 10), width=30)
    username_entry.pack(padx=40, pady=(0, 10), fill="x", ipady=5)
    username_entry.focus()
    
    tk.Label(root, text="Password:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5), fill="x")
    password_entry = tk.Entry(root, font=("Segoe UI", 10), width=30, show="*")
    password_entry.pack(padx=40, pady=(0, 10), fill="x", ipady=5)
    
    tk.Label(root, text="Confirm Password:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5), fill="x")
    confirm_password_entry = tk.Entry(root, font=("Segoe UI", 10), width=30, show="*")
    confirm_password_entry.pack(padx=40, pady=(0, 15), fill="x", ipady=5)
    
    message_label = tk.Label(root, text="", font=("Segoe UI", 9), fg=COLOR_ERROR, wraplength=370, justify="left")
    message_label.pack(pady=(0, 10))
    
    def handle_register():
        username = username_entry.get().strip()
        password = password_entry.get()
        confirm_password = confirm_password_entry.get()
        
        if not username or not password or not confirm_password:
            message_label.config(text="Please fill in all fields!")
            return
            
        is_valid, msg = validate_username(username)
        if not is_valid:
            message_label.config(text=msg)
            return
            
        is_valid, msg = validate_password(password)
        if not is_valid:
            message_label.config(text=msg)
            return
            
        if password != confirm_password:
            message_label.config(text="Passwords do not match!")
            return
            
        messagebox.showinfo("Success", f"Registration for user '{username}' completed successfully!")
        on_success()

    button_frame = tk.Frame(root)
    button_frame.pack(pady=20)
    btn_styles = get_button_styles()
    
    tk.Button(button_frame, text="Register", command=handle_register, **btn_styles).grid(row=0, column=0, padx=5, ipady=4)
    tk.Button(button_frame, text="Back", command=on_back, **btn_styles).grid(row=0, column=1, padx=5, ipady=4)
    
    login_frame = tk.Frame(root)
    login_frame.pack(pady=(10, 0))
    tk.Label(login_frame, text="Already have an account? ", font=("Segoe UI", 9)).pack(side="left")
    
    login_link = tk.Label(login_frame, text="Sign in here", font=("Segoe UI", 9, "underline"), fg="blue", cursor="hand2")
    login_link.pack(side="left")
    login_link.bind("<Button-1>", lambda e: on_navigate_login())