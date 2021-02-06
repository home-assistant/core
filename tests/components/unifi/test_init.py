"""Test UniFi setup process."""
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components import unifi
from homeassistant.components.unifi import async_flatten_entry_data
from homeassistant.components.unifi.const import CONF_CONTROLLER, DOMAIN as UNIFI_DOMAIN
from homeassistant.setup import async_setup_component

from .test_controller import CONTROLLER_DATA, ENTRY_CONFIG, setup_unifi_integration

from tests.common import MockConfigEntry, mock_coro


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a controller."""
    assert await async_setup_component(hass, UNIFI_DOMAIN, {}) is True
    assert UNIFI_DOMAIN not in hass.data


async def test_successful_config_entry(hass, aioclient_mock):
    """Test that configured options for a host are loaded via config entry."""
    await setup_unifi_integration(hass, aioclient_mock)
    assert hass.data[UNIFI_DOMAIN]


async def test_controller_fail_setup(hass):
    """Test that a failed setup still stores controller."""
    with patch("homeassistant.components.unifi.UniFiController") as mock_controller:
        mock_controller.return_value.async_setup = AsyncMock(return_value=False)
        await setup_unifi_integration(hass)

    assert hass.data[UNIFI_DOMAIN] == {}


async def test_controller_no_mac(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data=ENTRY_CONFIG,
        unique_id="1",
        version=1,
    )
    entry.add_to_hass(hass)
    mock_registry = Mock()
    with patch(
        "homeassistant.components.unifi.UniFiController"
    ) as mock_controller, patch(
        "homeassistant.helpers.device_registry.async_get_registry",
        return_value=mock_coro(mock_registry),
    ):
        mock_controller.return_value.async_setup = AsyncMock(return_value=True)
        mock_controller.return_value.mac = None
        assert await unifi.async_setup_entry(hass, entry) is True

    assert len(mock_controller.mock_calls) == 2

    assert len(mock_registry.mock_calls) == 0


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

    assert await unifi.async_unload_entry(hass, config_entry)
    assert not hass.data[UNIFI_DOMAIN]
