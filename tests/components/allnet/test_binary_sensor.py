"""Tests for the ALLNET binary sensor platform."""

from unittest.mock import MagicMock, patch

from allnet.models import Channel, ChannelKind
import pytest

from homeassistant.components.allnet.const import DOMAIN
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_UNIQUE_ID


@pytest.mark.asyncio
async def test_binary_sensor_entities_created(hass: HomeAssistant, setup_integration) -> None:
    """Test that binary sensor entities are created for BINARY_SENSOR channels."""
    state_door = hass.states.get("binary_sensor.allnet_test_device_door_contact")
    state_motion = hass.states.get("binary_sensor.allnet_test_device_motion_sensor")

    assert state_door is not None
    assert state_motion is not None


@pytest.mark.asyncio
async def test_binary_sensor_is_on_true(hass: HomeAssistant, setup_integration) -> None:
    """Test that is_on=True maps to STATE_ON."""
    state = hass.states.get("binary_sensor.allnet_test_device_motion_sensor")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.asyncio
async def test_binary_sensor_is_on_false(hass: HomeAssistant, setup_integration) -> None:
    """Test that is_on=False maps to STATE_OFF."""
    state = hass.states.get("binary_sensor.allnet_test_device_door_contact")
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.asyncio
async def test_binary_sensor_is_on_none_is_unavailable(
    hass: HomeAssistant, setup_integration, mock_allnet_client, mock_channels
) -> None:
    """Test that value=None makes binary sensor unavailable after coordinator refresh."""
    # Replace channels with one that has value=None
    null_channel = Channel(
        id="door_0",
        kind=ChannelKind.BINARY_SENSOR,
        name="Door Contact",
        value=None,
        raw={"info": {"chipid": "74", "unit": ""}, "digitalToText": "offen/geschlossen"},
    )
    mock_allnet_client.async_get_channels.return_value = (null_channel,)

    entry = setup_integration
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.allnet_test_device_door_contact")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.asyncio
async def test_binary_sensor_motion_device_class(hass: HomeAssistant, setup_integration) -> None:
    """Test that chipid=74 + 'erkannt' in digitalToText → MOTION device class."""
    state = hass.states.get("binary_sensor.allnet_test_device_motion_sensor")
    assert state is not None
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.MOTION


@pytest.mark.asyncio
async def test_binary_sensor_door_no_specific_device_class(
    hass: HomeAssistant, setup_integration
) -> None:
    """Test door_0: chipid=74 but no 'erkannt' in digitalToText → no device class."""
    state = hass.states.get("binary_sensor.allnet_test_device_door_contact")
    assert state is not None
    # chipid 74 with generic text → device_class is None (not set)
    assert state.attributes.get("device_class") is None


@pytest.mark.asyncio
async def test_binary_sensor_unique_id(hass: HomeAssistant, setup_integration) -> None:
    """Test that binary sensor entities have the correct unique_id."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{TEST_UNIQUE_ID}_door_0_binary_sensor"
    )
    assert entry is not None


@pytest.mark.asyncio
async def test_binary_sensor_name_based_device_class(
    hass: HomeAssistant, config_entry, mock_allnet_client, mock_device_info
) -> None:
    """Test name-based heuristics for binary sensor device class (opening)."""
    # Channel with "door" in name, chipid not 74 → name-based OPENING class
    door_channel = Channel(
        id="door_1",
        kind=ChannelKind.BINARY_SENSOR,
        name="door sensor",
        value=True,
        raw={"info": {"chipid": "50", "unit": ""}, "digitalToText": "on/off"},
    )
    mock_allnet_client.async_get_channels.return_value = (door_channel,)

    mock_session = MagicMock()
    with (
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
        patch(
            "homeassistant.components.allnet.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        await hass.config_entries.async_add(config_entry)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.allnet_test_device_door_sensor")
    assert state is not None
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.OPENING
