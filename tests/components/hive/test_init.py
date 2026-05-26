"""Tests for the Hive integration __init__."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.hive.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry

_ENTRY_DATA = {
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "password",
    "tokens": {
        "AuthenticationResult": {
            "AccessToken": "mock-access-token",
            "RefreshToken": "mock-refresh-token",
        },
        "ChallengeName": "SUCCESS",
    },
}

_HUB_BASE = {
    "device_id": "hive-hub-id",
    "hiveName": "Hive Hub",
    "deviceData": {
        "model": "Hub",
        "version": "1.2.3",
        "manufacturer": "Hive",
        "online": True,
    },
}


def _make_mock_hive(hub_extra: dict) -> MagicMock:
    """Return a mocked Hive instance.

    startSession returns a minimal devices dict.
    """
    hub_data = {**_HUB_BASE, **hub_extra}
    mock_hive = MagicMock()
    mock_hive.session.startSession = AsyncMock(return_value={"parent": [hub_data]})
    return mock_hive


async def test_hub_device_registers_mac_connection(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Hub device entry includes a MAC connection when macAddress is present."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive({"macAddress": "00:1C:2B:1C:2E:68"})

    with (
        patch(
            "homeassistant.components.hive.Hive",
            return_value=mock_hive,
        ),
        patch("homeassistant.components.hive.aiohttp_client.async_get_clientsession"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, "hive-hub-id")})
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "00:1c:2b:1c:2e:68") in device.connections


async def test_hub_device_no_mac_connection_when_absent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Hub device entry has no MAC connection when macAddress is absent."""
    entry = MockConfigEntry(domain=DOMAIN, data=_ENTRY_DATA)
    entry.add_to_hass(hass)

    mock_hive = _make_mock_hive({})  # no macAddress key

    with (
        patch(
            "homeassistant.components.hive.Hive",
            return_value=mock_hive,
        ),
        patch("homeassistant.components.hive.aiohttp_client.async_get_clientsession"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, "hive-hub-id")})
    assert device is not None
    assert not any(
        conn_type == dr.CONNECTION_NETWORK_MAC for conn_type, _ in device.connections
    )
