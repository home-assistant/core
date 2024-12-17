"""tplink conftest."""

from collections.abc import Generator
from unittest.mock import DEFAULT, AsyncMock, patch

from kasa import DeviceConfig
import pytest

from homeassistant.components.tplink import DOMAIN
from homeassistant.core import HomeAssistant

from . import (
    CREATE_ENTRY_DATA_LEGACY,
    CREDENTIALS_HASH_AES,
    CREDENTIALS_HASH_KLAP,
    DEVICE_CONFIG_AES,
    DEVICE_CONFIG_KLAP,
    IP_ADDRESS,
    IP_ADDRESS2,
    MAC_ADDRESS,
    MAC_ADDRESS2,
    _mocked_device,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_discovery():
    """Mock python-kasa discovery."""
    with patch.multiple(
        "homeassistant.components.tplink.Discover",
        discover=DEFAULT,
        discover_single=DEFAULT,
        try_connect_all=DEFAULT,
    ) as mock_discovery:
        device = _mocked_device(
            device_config=DeviceConfig.from_dict(DEVICE_CONFIG_KLAP.to_dict()),
            credentials_hash=CREDENTIALS_HASH_KLAP,
            alias="My Bulb",
        )
        devices = {
            "127.0.0.1": _mocked_device(
                device_config=DeviceConfig.from_dict(DEVICE_CONFIG_KLAP.to_dict()),
                credentials_hash=CREDENTIALS_HASH_KLAP,
                alias=None,
            )
        }
        mock_discovery["discover"].return_value = devices
        mock_discovery["discover_single"].return_value = device
        mock_discovery["try_connect_all"].return_value = device
        mock_discovery["mock_device"] = device
        yield mock_discovery


@pytest.fixture
def mock_connect():
    """Mock python-kasa connect."""
    with patch("homeassistant.components.tplink.Device.connect") as mock_connect:
        devices = {
            IP_ADDRESS: _mocked_device(
                device_config=DeviceConfig.from_dict(DEVICE_CONFIG_KLAP.to_dict()),
                credentials_hash=CREDENTIALS_HASH_KLAP,
                ip_address=IP_ADDRESS,
            ),
            IP_ADDRESS2: _mocked_device(
                device_config=DeviceConfig.from_dict(DEVICE_CONFIG_AES.to_dict()),
                credentials_hash=CREDENTIALS_HASH_AES,
                mac=MAC_ADDRESS2,
                ip_address=IP_ADDRESS2,
            ),
        }

        def get_device(config):
            nonlocal devices
            return devices[config.host]

        mock_connect.side_effect = get_device
        yield {"connect": mock_connect, "mock_devices": devices}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch.multiple(
        async_setup=DEFAULT,
        async_setup_entry=DEFAULT,
    ) as mock_setup_entry:
        mock_setup_entry["async_setup"].return_value = True
        mock_setup_entry["async_setup_entry"].return_value = True
        yield mock_setup_entry


@pytest.fixture
def mock_init() -> Generator[AsyncMock]:
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
        unique_id=MAC_ADDRESS,
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
