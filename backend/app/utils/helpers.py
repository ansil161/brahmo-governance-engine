import re
import secrets
import string
from typing import Any, Dict


def is_valid_email(email: str) -> bool:
    """Validate email syntax using a standard regular expression."""
    email_regex = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )
    return bool(email_regex.match(email))


def generate_random_token(length: int = 32) -> str:
    """Generate a secure random hex string for tokens."""
    return secrets.token_hex(length // 2)


def generate_random_password(length: int = 12) -> str:
    """Generate a secure temporary password."""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(characters) for _ in range(length))
