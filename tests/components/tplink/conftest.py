"""tplink conftest."""

from collections.abc import Generator
from unittest.mock import DEFAULT, AsyncMock, patch

import pytest

from homeassistant.components.tplink import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    CREATE_ENTRY_DATA_LEGACY,
    CREDENTIALS_HASH_AUTH,
    DEVICE_CONFIG_AUTH,
    _mocked_bulb,
)

from tests.common import MockConfigEntry, mock_device_registry, mock_registry


@pytest.fixture
def mock_discovery():
    """Mock python-kasa discovery."""
    device = _mocked_bulb(
        device_config=DEVICE_CONFIG_AUTH, credentials_hash=CREDENTIALS_HASH_AUTH
    )
    devices = {
        "127.0.0.1": _mocked_bulb(
            device_config=DEVICE_CONFIG_AUTH, credentials_hash=CREDENTIALS_HASH_AUTH
        )
    }
    with patch.multiple(
        "homeassistant.components.tplink.Discover",
        discover=DEFAULT,
        discover_single=DEFAULT,
    ) as mock_discovery:
        mock_discovery["discover"].return_value = devices
        mock_discovery["discover_single"].return_value = device
        mock_discovery["mock_device"] = device
        yield mock_discovery


@pytest.fixture
def mock_connect():
    """Mock python-kasa connect."""
    with patch("homeassistant.components.tplink.SmartDevice.connect") as mock_connect:
        device = _mocked_bulb(
            device_config=DEVICE_CONFIG_AUTH, credentials_hash=CREDENTIALS_HASH_AUTH
        )
        mock_connect.return_value = device
        yield {"connect": mock_connect, "mock_device": device}


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture(name="entity_reg")
def entity_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture(autouse=True)
def tplink_mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch("homeassistant.components.tplink.async_setup", return_value=True), patch(
        "homeassistant.components.tplink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_init() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch.multiple(
        "homeassistant.components.tplink",
        async_setup=DEFAULT,
        async_setup_entry=DEFAULT,
        async_unload_entry=DEFAULT,
    ) as mock_init:
        mock_init["async_setup"].return_value = True
        mock_init["async_setup_entry"].return_value = True
        mock_init["async_unload_entry"].return_value = True
        yield mock_init


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock ConfigEntry."""
    return MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data={**CREATE_ENTRY_DATA_LEGACY},
        unique_id="12:34:56:78:90",
    )


@pytest.fixture
async def mock_added_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init,
) -> MockConfigEntry:
    """Mock ConfigEntry that's been added to HA."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.config_entries.async_domains()
    return mock_config_entry
