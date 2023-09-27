"""Test the devolo Home Network integration setup."""
from unittest.mock import patch

from devolo_plc_api.exceptions.device import DeviceNotFound
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.button import DOMAIN as BUTTON
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER
from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.components.image import DOMAIN as IMAGE
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.components.update import DOMAIN as UPDATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms

from . import configure_integration
from .const import IP
from .mock import MockDevice

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_device")
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ), patch("homeassistant.core.EventBus.async_listen_once"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_device")
async def test_setup_without_password(hass: HomeAssistant) -> None:
    """Test setup entry without a device password set like used before HA Core 2022.06."""
    config = {
        CONF_IP_ADDRESS: IP,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ), patch("homeassistant.core.EventBus.async_listen_once"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.LOADED


async def test_setup_device_not_found(hass: HomeAssistant) -> None:
    """Test setup entry."""
    entry = configure_integration(hass)
    with patch(
        "homeassistant.components.devolo_home_network.Device.async_connect",
        side_effect=DeviceNotFound(IP),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_device")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload entry."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_hass_stop(hass: HomeAssistant, mock_device: MockDevice) -> None:
    """Test homeassistant stop event."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_device.async_disconnect.assert_called_once()


@pytest.mark.parametrize(
    ("device", "expected_platforms"),
    [
        [
            "mock_device",
            (BINARY_SENSOR, BUTTON, DEVICE_TRACKER, IMAGE, SENSOR, SWITCH, UPDATE),
        ],
        [
            "mock_repeater_device",
            (BUTTON, DEVICE_TRACKER, IMAGE, SENSOR, SWITCH, UPDATE),
        ],
        ["mock_nonwifi_device", (BINARY_SENSOR, BUTTON, SENSOR, SWITCH, UPDATE)],
    ],
)
async def test_platforms(
    hass: HomeAssistant,
    device: str,
    expected_platforms: set[str],
    request: pytest.FixtureRequest,
) -> None:
    """Test platform assembly."""
    request.getfixturevalue(device)
    entry = configure_integration(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    platforms = [platform.domain for platform in async_get_platforms(hass, DOMAIN)]
    assert len(platforms) == len(expected_platforms)
    assert all(platform in platforms for platform in expected_platforms)
