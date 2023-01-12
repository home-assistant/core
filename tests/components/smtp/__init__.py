"""Tests for the smtp component."""
from homeassistant.components.smtp.const import (
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

MOCK_CONFIG = {
    CONF_NAME: "smtp",
    CONF_SENDER: "test@test.com",
    CONF_SENDER_NAME: "Home Assistant",
    CONF_RECIPIENT: ["recip1@example.com", "testrecip@test.com"],
    CONF_SERVER: "server",
    CONF_PORT: 587,
    CONF_TIMEOUT: 5,
    CONF_ENCRYPTION: "tls",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_DEBUG: True,
    CONF_VERIFY_SSL: True,
}

MOCK_USER_INPUT = {
    CONF_NAME: "smtp",
    CONF_SERVER: "server",
    CONF_PORT: 587,
    CONF_ENCRYPTION: "starttls",
    CONF_USERNAME: "example@mail.com",
    CONF_PASSWORD: "password",
    CONF_DEBUG: True,
    CONF_VERIFY_SSL: True,
}
