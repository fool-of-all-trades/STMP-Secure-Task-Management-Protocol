import re

# Walidacja nazwy użytkownika
def validate_username(username):
    if len(username) < 3:
        return False, "Username must be at least 3 characters long."
    if len(username) > 30:
        return False, "Username cannot be longer than 30 characters."
    if not re.match("^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores."
    return True, ""


# Walidacja hasła
def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if len(password) > 128:
        return False, "Password cannot be longer than 128 characters."
    return True, ""


# Walidacja wspólna (username + password)
def run_common_validation(username, password):
    if not username or not password:
        return False, "Please fill in all fields!"

    is_valid, msg = validate_username(username)
    if not is_valid:
        return False, msg

    is_valid, msg = validate_password(password)
    if not is_valid:
        return False, msg

    return True, ""