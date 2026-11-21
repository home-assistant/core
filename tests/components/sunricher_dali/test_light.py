"""Test the Sunricher DALI light platform."""

from typing import Any
from unittest.mock import MagicMock

from PySrDaliGateway import CallbackEventType
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    SnapshotAssertion,
    snapshot_platform,
)

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    LightService,
    LightServiceArgument,
)
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import find_device_listener, trigger_availability_callback

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


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.LIGHT]


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
        LightService.TURN_ON,
        {TargetKey.ENTITY_ID: TEST_DIMMER_ENTITY_ID},
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
        LightService.TURN_OFF,
        {TargetKey.ENTITY_ID: TEST_DIMMER_ENTITY_ID},
        blocking=True,
    )

    mock_devices[0].turn_off.assert_called_once()


@pytest.mark.parametrize(
    ("service", "method"),
    [
        pytest.param(SERVICE_TURN_ON, "turn_on", id="turn_on"),
        pytest.param(SERVICE_TURN_OFF, "turn_off", id="turn_off"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_light_action_gateway_disconnected(
    hass: HomeAssistant,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    service: str,
    method: str,
) -> None:
    """Test light actions raise when the gateway is disconnected."""
    mock_gateway.is_connected = False

    with pytest.raises(HomeAssistantError, match="The DALI gateway is not connected"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: TEST_DIMMER_ENTITY_ID},
            blocking=True,
        )

    getattr(mock_devices[0], method).assert_not_called()


async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_devices: list[MagicMock],
) -> None:
    """Test turning on light with brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        LightService.TURN_ON,
        {
            TargetKey.ENTITY_ID: TEST_DIMMER_ENTITY_ID,
            LightServiceArgument.BRIGHTNESS: 128,
        },
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
    """Test availability changes are reflected in entity state."""
    trigger_availability_callback(mock_devices[0], False)
    await hass.async_block_till_done()
    assert (state := hass.states.get(TEST_DIMMER_ENTITY_ID))
    assert state.state == "unavailable"

    trigger_availability_callback(mock_devices[0], True)
    await hass.async_block_till_done()
    assert (state := hass.states.get(TEST_DIMMER_ENTITY_ID))
    assert state.state != "unavailable"
