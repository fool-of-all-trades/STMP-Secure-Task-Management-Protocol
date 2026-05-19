import tkinter as tk
from tkinter import messagebox

APP_NAME = "STMP Secure Task Manager"
DESCRIPTION = (
    "Welcome to STMP – Secure Task Manager.\n"
    "A simple welcome screen for the application."
)

PROJECT_INFO = (
    "Project: STMP Secure Task Manager\n"
    "Model: Client-Server with STMP/1.0 protocol\n"
    "Technologies: Python + TLS + JSON + SQLite/DB"
)


def show_info():
    messagebox.showinfo("App Information", PROJECT_INFO)


def show_next_steps():
    messagebox.showinfo("Next Screen", "The Login/Registration screen will be displayed here.\n")

# Utility function to center the window on the screen
def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    window.geometry(f"{width}x{height}+{x}+{y}")


def main():
    root = tk.Tk()
    root.title(APP_NAME)
    
    # Window size setup and centering
    window_width = 500
    window_height = 280
    center_window(root, window_width, window_height)
    root.resizable(False, False)

    # Title label
    title_label = tk.Label(root, text=APP_NAME, font=("Segoe UI", 18, "bold"), fg="#1f4e79")
    title_label.pack(pady=(35, 12))

    # Description label
    description_label = tk.Label(
        root,
        text=DESCRIPTION,
        font=("Segoe UI", 11),
        justify="center",
        wraplength=520,
    )
    description_label.pack(padx=20, pady=(0, 20))

    # Button frame
    button_frame = tk.Frame(root)
    button_frame.pack(pady=(0, 30))

    # Common styling parameters for all buttons
    btn_styles = {
        "width": 16,
        "font": ("Segoe UI", 10, "bold"),
        "bg": "#1f4e79",
        "fg": "white",
        "activebackground": "#153552",
        "activeforeground": "white",
        "relief": "flat",
        "bd": 0
    }

    start_button = tk.Button(
        button_frame,
        text="Get Started",
        command=show_next_steps,
        **btn_styles
    )
    start_button.grid(row=0, column=0, padx=8, ipady=4)

    info_button = tk.Button(
        button_frame,
        text="Info",
        command=show_info,
        **btn_styles
    )
    info_button.grid(row=0, column=1, padx=8, ipady=4)

    quit_button = tk.Button(
        button_frame,
        text="Quit",
        command=root.destroy,
        **btn_styles
    )
    quit_button.grid(row=0, column=2, padx=8, ipady=4)

    root.mainloop()


if __name__ == "__main__":
    main()