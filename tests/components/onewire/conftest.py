"""Provide common 1-Wire fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyownet.protocol import ConnError
import pytest

from homeassistant.components.onewire.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import MOCK_OWPROXY_DEVICES

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onewire.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="device_id", params=MOCK_OWPROXY_DEVICES.keys())
def get_device_id(request: pytest.FixtureRequest) -> str:
    """Parametrize device id."""
    return request.param


@pytest.fixture(name="config_entry")
def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
        },
        options={
            "device_options": {
                "28.222222222222": {"precision": "temperature9"},
                "28.222222222223": {"precision": "temperature5"},
            }
        },
        entry_id="2",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="owproxy")
def get_owproxy() -> MagicMock:
    """Mock owproxy."""
    with patch("homeassistant.components.onewire.onewirehub.protocol.proxy") as owproxy:
        yield owproxy


@pytest.fixture(name="owproxy_with_connerror")
def get_owproxy_with_connerror() -> MagicMock:
    """Mock owproxy."""
    with patch(
        "homeassistant.components.onewire.onewirehub.protocol.proxy",
        side_effect=ConnError,
    ) as owproxy:
        yield owproxy
