"""Tests for the LIVISI Smart Home integration."""

from unittest.mock import MagicMock, patch

from livisi import LivisiConnection, LivisiController

from homeassistant.const import CONF_HOST, CONF_PASSWORD

VALID_CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_PASSWORD: "test",
}

CONTROLLER = LivisiController(
    controller_type="Classic",
    serial_number="1234",
    os_version="1.0",
    is_v2=False,
    is_v1=True,
)


def mocked_livisi_connect():
    """Create mock for a LIVISI connection."""
    connection = MagicMock(spec=LivisiConnection)
    connection.controller = CONTROLLER
    return patch(
        "homeassistant.components.livisi.config_flow.livisi_connect",
        return_value=connection,
    )


def mocked_livisi_setup_entry():
    """Create mock for LIVISI setup entry."""
    return patch(
        "homeassistant.components.livisi.async_setup_entry",
        return_value=True,
    )
