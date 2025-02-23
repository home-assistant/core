"""tplink conftest."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import DEFAULT, AsyncMock, patch

from kasa import DeviceConfig, Module
import pytest

from homeassistant.components.tplink import DOMAIN
from homeassistant.core import HomeAssistant

from . import _mocked_device
from .const import (
    ALIAS_CAMERA,
    CREATE_ENTRY_DATA_AES_CAMERA,
    CREATE_ENTRY_DATA_LEGACY,
    CREDENTIALS_HASH_AES,
    CREDENTIALS_HASH_KLAP,
    DEVICE_CONFIG_AES,
    DEVICE_CONFIG_AES_CAMERA,
    DEVICE_CONFIG_KLAP,
    IP_ADDRESS,
    IP_ADDRESS2,
    IP_ADDRESS3,
    MAC_ADDRESS,
    MAC_ADDRESS2,
    MAC_ADDRESS3,
    MODEL_CAMERA,
)

from tests.common import MockConfigEntry


@contextmanager
def override_side_effect(mock: AsyncMock, effect):
    """Temporarily override a mock side effect and replace afterwards."""
    try:
        default_side_effect = mock.side_effect
        mock.side_effect = effect
        yield mock
    finally:
        mock.side_effect = default_side_effect


def _get_mock_devices():
    return {
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
        IP_ADDRESS3: _mocked_device(
            device_config=DeviceConfig.from_dict(DEVICE_CONFIG_AES_CAMERA.to_dict()),
            credentials_hash=CREDENTIALS_HASH_AES,
            mac=MAC_ADDRESS3,
            ip_address=IP_ADDRESS3,
            modules=[Module.Camera],
            alias=ALIAS_CAMERA,
            model=MODEL_CAMERA,
        ),
    }


@pytest.fixture
def mock_discovery():
    """Mock python-kasa discovery."""
    with patch.multiple(
        "homeassistant.components.tplink.Discover",
        discover=DEFAULT,
        discover_single=DEFAULT,
        try_connect_all=DEFAULT,
    ) as mock_discovery:
        devices = _get_mock_devices()

        def get_device(host, **kwargs):
            return devices[host]

        mock_discovery["discover"].return_value = devices
        mock_discovery["discover_single"].side_effect = get_device
        mock_discovery["try_connect_all"].side_effect = get_device
        mock_discovery["mock_devices"] = devices
        yield mock_discovery


@pytest.fixture
def mock_connect():
    """Mock python-kasa connect."""
    with patch("homeassistant.components.tplink.Device.connect") as mock_connect:
        devices = _get_mock_devices()

        def get_device(config):
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
def mock_init() -> Generator[dict[str, AsyncMock]]:
    """Override async_setup and async_setup_entry.

    This fixture must be declared before the hass fixture to avoid errors
    in the logs during teardown of the hass fixture which calls async_unload.
    """
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
def mock_camera_config_entry() -> MockConfigEntry:
    """Mock camera ConfigEntry."""
    return MockConfigEntry(
        title="TPLink",
        domain=DOMAIN,
        data={**CREATE_ENTRY_DATA_AES_CAMERA},
        unique_id=MAC_ADDRESS3,
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
