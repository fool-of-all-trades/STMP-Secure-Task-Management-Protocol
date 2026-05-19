"""Common authentication utilities, validators, and window managers"""
import re
import tkinter as tk

COLOR_PRIMARY = "#1f4e79"
COLOR_PRIMARY_DARK = "#153552"
COLOR_ERROR = "#d32f2f"
COLOR_SUCCESS = "#388e3c"

def validate_username(username):
    """Validate username format"""
    if len(username) < 3:
        return False, "Username must be at least 3 characters long."
    if len(username) > 30:
        return False, "Username cannot be longer than 30 characters."
    if not re.match("^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores."
    return True, ""

def validate_password(password):
    """Validate password format"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password cannot be longer than 128 characters."
    return True, ""

def get_button_styles():
    """Get common button styling parameters"""
    return {
        "width": 14,
        "font": ("Segoe UI", 10, "bold"),
        "bg": COLOR_PRIMARY,
        "fg": "white",
        "activebackground": COLOR_PRIMARY_DARK,
        "activeforeground": "white",
        "relief": "flat",
        "bd": 0
    }

def prepare_screen(root, width, height, title):
    """Clears the screen, sets the window dimension, and centers it perfectly."""
    for widget in root.winfo_children():
        widget.destroy()
        
    root.title(title)
    root.resizable(False, False)
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    root.geometry(f"{width}x{height}+{x}+{y}")