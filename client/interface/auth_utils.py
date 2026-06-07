import tkinter as tk

COLOR_PRIMARY = "#1f4e79"
COLOR_PRIMARY_DARK = "#153552"
COLOR_ERROR = "#d32f2f"
COLOR_SUCCESS = "#388e3c"


# Styl ogólny dla przycisków
def get_button_styles():
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


# Przygotowanie okna aplikacji
def prepare_screen(root, width, height, title):
    for widget in root.winfo_children():
        widget.destroy()

    root.title(title)
    root.resizable(False, False)

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)

    root.geometry(f"{width}x{height}+{x}+{y}")


# Formularz uwierzytelniania
def create_auth_base_form(root, width, height, window_title, form_title, main_btn_text, on_main_action, on_back,
                          nav_text, nav_link_text, on_nav_click):
    prepare_screen(root, width, height, window_title)

    title_label = tk.Label(root, text=form_title, font=("Segoe UI", 18, "bold"), fg=COLOR_PRIMARY)
    title_label.pack(pady=(20, 15))

    # Pole Username
    tk.Label(root, text="Username:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5), fill="x")
    username_entry = tk.Entry(root, font=("Segoe UI", 10), width=30)
    username_entry.pack(padx=40, pady=(0, 10), fill="x", ipady=5)
    username_entry.focus()

    # Pole Password
    tk.Label(root, text="Password:", font=("Segoe UI", 10), anchor="w").pack(padx=40, pady=(0, 5), fill="x")
    password_entry = tk.Entry(root, font=("Segoe UI", 10), width=30, show="*")
    password_entry.pack(padx=40, pady=(0, 10), fill="x", ipady=5)

    # Miejsce na dodatkowe pola (potwierdzenie hasła w rejestracji)
    extra_fields_frame = tk.Frame(root)
    extra_fields_frame.pack(fill="x")

    # Etykieta na błędy
    message_label = tk.Label(root, text="", font=("Segoe UI", 9), fg=COLOR_ERROR, wraplength=370, justify="left")
    message_label.pack(pady=(10, 0))

    # Przyciski dolne
    button_frame = tk.Frame(root)
    button_frame.pack(pady=15)
    btn_styles = get_button_styles()

    tk.Button(button_frame, text=main_btn_text, command=on_main_action, **btn_styles).grid(row=0, column=0, padx=5,
                                                                                           ipady=4)
    tk.Button(button_frame, text="Back", command=on_back, **btn_styles).grid(row=0, column=1, padx=5, ipady=4)

    # Link nawigacyjny
    nav_frame = tk.Frame(root)
    nav_frame.pack(pady=(5, 0))
    tk.Label(nav_frame, text=nav_text, font=("Segoe UI", 9)).pack(side="left")

    link = tk.Label(nav_frame, text=nav_link_text, font=("Segoe UI", 9, "underline"), fg="blue", cursor="hand2")
    link.pack(side="left")
    link.bind("<Button-1>", lambda e: on_nav_click())

    return username_entry, password_entry, message_label, extra_fields_frame