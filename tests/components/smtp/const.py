""""Shared constants for SMTP tests."""

from homeassistant.components.smtp.const import DOMAIN

MOCKED_CONFIG_ENTRY_DATA = {
    "name": DOMAIN,
    "recipient": ["test@example.com"],
    "sender": "test@example.com",
    "server": "localhost",
    "port": 587,
    "encryption": "starttls",
    "debug": False,
    "verify_ssl": True,
    "timeout": 5,
}

MOCKED_USER_ADVANCED_DATA = {
    "name": DOMAIN,
    "recipient": ["test@example.com"],
    "sender": "test@example.com",
    "server": "localhost",
    "port": 587,
    "encryption": "starttls",
    "debug": False,
    "verify_ssl": True,
    "timeout": 5,
}

MOCKED_USER_BASIC_DATA = {
    "name": DOMAIN,
    "recipient": ["test@example.com"],
    "sender": "test@example.com",
    "server": "localhost",
    "port": 587,
    "encryption": "starttls",
}
