"""Fixtures for testing the Orvibo integration (core version)."""

from unittest.mock import patch

# The orvibo library executes a global UDP socket bind on import.
# We force the import here inside a patch context manager to prevent parallel
# CI test workers from crashing with 'OSError: [Errno 98] Address already in use'.
with patch("socket.socket.bind"):
    import orvibo.s20  # noqa: F401

import pytest

from homeassistant.components.orvibo.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC

from tests.common import MockConfigEntry


@pytest.fixture
def mock_s20():
    """Mock the Orvibo S20 class."""
    with patch("homeassistant.components.orvibo.config_flow.S20") as mock_class:
        yield mock_class


@pytest.fixture
def mock_discover():
    """Mock Orvibo S20 discovery returning multiple devices."""
    with patch("homeassistant.components.orvibo.config_flow.discover") as mock_func:
        mock_func.return_value = {
            "192.168.1.100": {"mac": b"\xac\xcf\x23\x12\x34\x56"},
            "192.168.1.101": {"mac": b"\xac\xcf\x23\x78\x9a\xbc"},
        }
        yield mock_func


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for an Orvibo S20 switch."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Orvibo (192.168.1.10)",
        data={CONF_HOST: "192.168.1.10", CONF_MAC: "aa:bb:cc:dd:ee:ff"},
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_setup_entry():
    """Override async_setup_entry so config flow tests don't try to setup the integration."""
    with patch(
        "homeassistant.components.orvibo.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
