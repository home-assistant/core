"""Test the Sunricher DALI light platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from PySrDaliGateway import CallbackEventType
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import find_device_listener

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

TEST_DIMMER_ENTITY_ID = "light.dimmer_0000_02"
TEST_DIMMER_DEVICE_ID = "01010000026A242121110E"
TEST_CCT_DEVICE_ID = "01020000036A242121110E"
TEST_HS_DEVICE_ID = "01030000046A242121110E"
TEST_RGBW_DEVICE_ID = "01040000056A242121110E"


def _trigger_light_status_callback(
    device: MagicMock, device_id: str, status: dict[str, Any]
) -> None:
    """Trigger the light status callbacks registered on the device mock."""
    callback = find_device_listener(device, CallbackEventType.LIGHT_STATUS)
    callback(status)


def _trigger_availability_callback(
    device: MagicMock, device_id: str, available: bool
) -> None:
    """Trigger the availability callbacks registered on the device mock."""
    callback = find_device_listener(device, CallbackEventType.ONLINE_STATUS)
    callback(available)


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.LIGHT]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.sunricher_dali._PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 5

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id is not None


async def test_turn_on_light(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test turning on a light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_DIMMER_ENTITY_ID},
        blocking=True,
    )

    mock_devices[0].turn_on.assert_called_once()


async def test_turn_off_light(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test turning off a light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_DIMMER_ENTITY_ID},
        blocking=True,
    )

    mock_devices[0].turn_off.assert_called_once()


async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test turning on light with brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_DIMMER_ENTITY_ID, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    mock_devices[0].turn_on.assert_called_once_with(
        brightness=128,
        color_temp_kelvin=None,
        hs_color=None,
        rgbw_color=None,
    )


async def test_callback_registration(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test that callbacks are properly registered and triggered."""
    state_before = hass.states.get(TEST_DIMMER_ENTITY_ID)
    assert state_before is not None

    status_update: dict[str, Any] = {"is_on": True, "brightness": 128}
    _trigger_light_status_callback(
        mock_devices[0], TEST_DIMMER_DEVICE_ID, status_update
    )
    await hass.async_block_till_done()

    state_after = hass.states.get(TEST_DIMMER_ENTITY_ID)
    assert state_after is not None
    assert state_after.state == "on"
    assert state_after.attributes.get("brightness") == 128


@pytest.mark.parametrize(
    ("device_id", "status_update"),
    [
        (TEST_CCT_DEVICE_ID, {"color_temp_kelvin": 3000}),
        (TEST_HS_DEVICE_ID, {"hs_color": (120.0, 50.0)}),
        (TEST_RGBW_DEVICE_ID, {"rgbw_color": (255, 128, 64, 32)}),
        (TEST_RGBW_DEVICE_ID, {"white_level": 200}),
    ],
    ids=["cct_color_temp", "hs_color", "rgbw_color", "rgbw_white_level"],
)
async def test_status_updates(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
    device_id: str,
    status_update: dict[str, Any],
) -> None:
    """Test various status updates for different device types."""
    device = next(d for d in mock_devices if d.dev_id == device_id)
    _trigger_light_status_callback(device, device_id, status_update)
    await hass.async_block_till_done()


async def test_device_availability(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test device availability changes."""
    _trigger_availability_callback(mock_devices[0], TEST_DIMMER_DEVICE_ID, False)
    await hass.async_block_till_done()
    assert (state := hass.states.get(TEST_DIMMER_ENTITY_ID))
    assert state.state == "unavailable"

    _trigger_availability_callback(mock_devices[0], TEST_DIMMER_DEVICE_ID, True)
    await hass.async_block_till_done()
    assert (state := hass.states.get(TEST_DIMMER_ENTITY_ID))
    assert state.state != "unavailable"
