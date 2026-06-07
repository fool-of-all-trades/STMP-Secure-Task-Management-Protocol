from client.actions.validators import run_common_validation
from shared.error_codes import ERROR_CODES

# Pobranie tekstu na podstawie kodu błędu
def get_action_error(response: dict, fallback: str) -> str:
    payload = response.get("payload", {})
    error_code = payload.get("error_code")
    if error_code in ERROR_CODES:
        return f"{ERROR_CODES[error_code]} ({payload.get('message', fallback)})"
    return payload.get("message", fallback)


# Logowanie
def perform_login(coordinator, username, password):
    is_valid, msg = run_common_validation(username, password)
    if not is_valid:
        return {"success": False, "message": msg}

    future = coordinator.run_async(
        coordinator.client.request("LOGIN", {"username": username, "password": password})
    )
    try:
        response = future.result(timeout=5.0)
        if response.get("type") == "LOGIN_OK":
            return {"success": True}

        # Parsowanie błędu przez słownik kodów
        return {"success": False, "message": get_action_error(response, "Login failed.")}
    except Exception as e:
        return {"success": False, "message": f"Network error: {str(e)}"}


# Rejestrowanie
def perform_register(coordinator, username, password, confirm_password):
    is_valid, msg = run_common_validation(username, password)
    if not is_valid:
        return {"success": False, "message": msg}

    if not confirm_password:
        return {"success": False, "message": "Please fill in all fields!"}

    if password != confirm_password:
        return {"success": False, "message": "Passwords do not match!"}

    future = coordinator.run_async(
        coordinator.client.request("REGISTER", {"username": username, "password": password})
    )
    try:
        response = future.result(timeout=5.0)
        if response.get("type") == "REGISTER_OK":
            return {"success": True}

        # Parsowanie błędu przez słownik kodów
        return {"success": False, "message": get_action_error(response, "Registration failed.")}
    except Exception as e:
        return {"success": False, "message": f"Network error: {str(e)}"}


# Ponowne logowanie po utracie sesji
def perform_reauth(coordinator, username, password):
    if not password:
        return {"success": False, "message": "Password cannot be empty."}

    connect_future = coordinator.run_async(coordinator.client.connect())
    try:
        connected = connect_future.result(timeout=6.0)
        if not connected:
            return {"success": False, "message": "Could not reconnect to server."}
    except Exception as e:
        return {"success": False, "message": f"Network error: {str(e)}"}

    login_future = coordinator.run_async(
        coordinator.client.request("LOGIN", {"username": username, "password": password})
    )
    try:
        response = login_future.result(timeout=5.0)
        if response.get("type") == "LOGIN_OK":
            return {"success": True}

        # Parsowanie błędu przez słownik kodów
        return {"success": False, "message": get_action_error(response, "Login failed.")}
    except Exception as e:
        return {"success": False, "message": f"Network error: {str(e)}"}