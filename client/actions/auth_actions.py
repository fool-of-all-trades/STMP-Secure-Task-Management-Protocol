from client.actions.validators import run_common_validation

# Logowanie przez STMP i zwraca słownik
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
        payload = response.get("payload", {})
        return {"success": False, "message": payload.get("message", "Login failed.")}
    except Exception as e:
        return {"success": False, "message": f"Network error: {str(e)}"}

# Rejestrowanie przez STMP i zwraca słownik
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
        payload = response.get("payload", {})
        return {"success": False, "message": payload.get("message", "Registration failed.")}
    except Exception as e:
        return {"success": False, "message": f"Network error: {str(e)}"}

# Ponowne logowanie po utracie sesji (nowe połączenie TCP/TLS > logowanie > słownik)
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
        payload = response.get("payload", {})
        return {"success": False, "message": payload.get("message", "Login failed.")}
    except Exception as e:
        return {"success": False, "message": f"Network error: {str(e)}"}