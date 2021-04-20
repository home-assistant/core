"""Test UniFi setup process."""
from unittest.mock import AsyncMock, patch

from homeassistant.components import unifi
from homeassistant.components.unifi import async_flatten_entry_data
from homeassistant.components.unifi.const import CONF_CONTROLLER, DOMAIN as UNIFI_DOMAIN
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.setup import async_setup_component

from .test_controller import (
    CONTROLLER_DATA,
    DEFAULT_CONFIG_ENTRY_ID,
    ENTRY_CONFIG,
    setup_unifi_integration,
)

from tests.common import MockConfigEntry


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a controller."""
    assert await async_setup_component(hass, UNIFI_DOMAIN, {}) is True
    assert UNIFI_DOMAIN not in hass.data


async def test_successful_config_entry(hass, aioclient_mock):
    """Test that configured options for a host are loaded via config entry."""
    await setup_unifi_integration(hass, aioclient_mock, unique_id=None)
    assert hass.data[UNIFI_DOMAIN]


async def test_controller_fail_setup(hass):
    """Test that a failed setup still stores controller."""
    with patch("homeassistant.components.unifi.UniFiController") as mock_controller:
        mock_controller.return_value.async_setup = AsyncMock(return_value=False)
        await setup_unifi_integration(hass)

    assert hass.data[UNIFI_DOMAIN] == {}


async def test_controller_mac(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN, data=ENTRY_CONFIG, unique_id="1", entry_id=1
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.unifi.UniFiController") as mock_controller:
        mock_controller.return_value.async_setup = AsyncMock(return_value=True)
        mock_controller.return_value.mac = "mac1"
        assert await unifi.async_setup_entry(hass, entry) is True

    assert len(mock_controller.mock_calls) == 2

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, connections={(CONNECTION_NETWORK_MAC, "mac1")}
    )
    assert device.manufacturer == "Ubiquiti Networks"
    assert device.model == "UniFi Controller"
    assert device.name == "UniFi Controller"
    assert device.sw_version is None


async def test_flatten_entry_data(hass):
    """Verify entry data can be flattened."""
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data={CONF_CONTROLLER: CONTROLLER_DATA},
    )
    await async_flatten_entry_data(hass, entry)

    assert entry.data == ENTRY_CONFIG


async def test_unload_entry(hass, aioclient_mock):
    """Test being able to unload an entry."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    assert hass.data[UNIFI_DOMAIN]

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert not hass.data[UNIFI_DOMAIN]


async def test_wireless_clients(hass, hass_storage, aioclient_mock):
    """Verify wireless clients class."""
    hass_storage[unifi.STORAGE_KEY] = {
        "version": unifi.STORAGE_VERSION,
        "data": {
            DEFAULT_CONFIG_ENTRY_ID: {
                "wireless_devices": ["00:00:00:00:00:00", "00:00:00:00:00:01"]
            }
        },
    }

    client_1 = {
        "hostname": "client_1",
        "ip": "10.0.0.1",
        "is_wired": False,
        "mac": "00:00:00:00:00:01",
    }
    client_2 = {
        "hostname": "client_2",
        "ip": "10.0.0.2",
        "is_wired": False,
        "mac": "00:00:00:00:00:02",
    }
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=[client_1, client_2]
    )

    for mac in [
        "00:00:00:00:00:00",
        "00:00:00:00:00:01",
        "00:00:00:00:00:02",
    ]:
        assert (
            mac
            in hass_storage[unifi.STORAGE_KEY]["data"][config_entry.entry_id][
                "wireless_devices"
            ]
        )
