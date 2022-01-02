"""Provide common 1-Wire fixtures."""
from unittest.mock import MagicMock, patch

from pyownet.protocol import ConnError
import pytest

from homeassistant.components.onewire.const import (
    CONF_MOUNT_DIR,
    CONF_TYPE_OWSERVER,
    CONF_TYPE_SYSBUS,
    DEFAULT_SYSBUS_MOUNT_DIR,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import MOCK_OWPROXY_DEVICES

from tests.common import MockConfigEntry


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
            CONF_TYPE: CONF_TYPE_OWSERVER,
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1234,
        },
        options={},
        entry_id="2",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="sysbus_config_entry")
def get_sysbus_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_TYPE: CONF_TYPE_SYSBUS,
            CONF_MOUNT_DIR: DEFAULT_SYSBUS_MOUNT_DIR,
        },
        unique_id=f"{CONF_TYPE_SYSBUS}:{DEFAULT_SYSBUS_MOUNT_DIR}",
        options={},
        entry_id="3",
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


@pytest.fixture(name="sysbus")
def get_sysbus() -> MagicMock:
    """Mock sysbus."""
    with patch(
        "homeassistant.components.onewire.onewirehub.os.path.isdir", return_value=True
    ):
        yield
