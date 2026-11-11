"""The tests for the Ring switch platform."""

from typing import Any

import pytest
from pytest_homeassistant.common import snapshot_platform
from ring_doorbell import RingCapability
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ring.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import MockConfigEntry, setup_platform


class BadChimeDoorbell:
    """Doorbell whose chime type is unknown to ring_doorbell."""

    family = "doorbots"
    id = 987654321
    device_api_id = 987654321
    device_id = "aa:bb:cc:dd:ee:ff"
    name = "Bad Chime Doorbell"

    @property
    def existing_doorbell_type(self) -> str:
        """Mimic ring_doorbell raising for an unknown chime type."""
        raise KeyError(3)

    def has_capability(self, capability: RingCapability) -> bool:
        """Return False for all capabilities."""
        return False


class ChimeCapabilityLostDoorbell:
    """Doorbell whose chime enabled-state read raises after setup."""

    family = "doorbots"
    id = 987654322
    device_api_id = 987654322
    device_id = "aa:bb:cc:dd:ee:00"
    name = "Chime Capability Lost Doorbell"
    model = "doorbots"
    existing_doorbell_type = "Mechanical"

    @property
    def existing_doorbell_type_enabled(self) -> bool:
        """Mimic ring_doorbell raising when the chime type becomes unknown."""
        raise KeyError(3)

    async def async_set_existing_doorbell_type_enabled(self, value: bool) -> None:
        """Mimic ring_doorbell raising when the chime type becomes unknown."""
        raise KeyError(3)

    def has_capability(self, capability: RingCapability) -> bool:
        """Return False for all capabilities."""
        return False


@pytest.mark.usefixtures("mock_ring_client")
async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""

    mock_config_entry.add_to_hass(hass)
    await setup_platform(hass, Platform.SWITCH)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("switch.front_door_in_home_chime"),
        ("switch.front_motion_detection"),
    ],
)
@pytest.mark.usefixtures("mock_ring_client")
async def test_switch_can_be_turned_on_and_off(hass: HomeAssistant, entity_id) -> None:
    """Tests the switch turns on and off correctly."""
    await setup_platform(hass, Platform.SWITCH)

    assert hass.states.get(entity_id)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_ring_client")
async def test_switch_setup_succeeds_with_unknown_chime_type(
    hass: HomeAssistant, mock_ring_devices: Any
) -> None:
    """Test that an unknown doorbell chime type does not abort switch setup."""
    mock_ring_devices.all_devices.append(BadChimeDoorbell())

    await setup_platform(hass, Platform.SWITCH)

    assert hass.states.get("switch.front_motion_detection")
    assert not hass.states.get("switch.bad_chime_doorbell_in_home_chime")


@pytest.mark.usefixtures("mock_ring_client")
async def test_in_home_chime_unknown_when_type_becomes_unreadable(
    hass: HomeAssistant, mock_ring_devices: Any
) -> None:
    """Test that an in-home chime switch reads as unknown when its type becomes unreadable."""
    mock_ring_devices.all_devices.append(ChimeCapabilityLostDoorbell())

    await setup_platform(hass, Platform.SWITCH)

    state = hass.states.get("switch.chime_capability_lost_doorbell_in_home_chime")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_ring_client")
async def test_in_home_chime_toggle_errors_when_type_unreadable(
    hass: HomeAssistant, mock_ring_devices: Any
) -> None:
    """Test that toggling raises a translated error when the chime type becomes unreadable."""
    mock_ring_devices.all_devices.append(ChimeCapabilityLostDoorbell())

    await setup_platform(hass, Platform.SWITCH)

    state = hass.states.get("switch.chime_capability_lost_doorbell_in_home_chime")
    assert state
    assert state.state == STATE_UNKNOWN

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": state.entity_id},
            blocking=True,
        )
    assert err.value.translation_key == "chime_type_unknown"
    assert err.value.translation_domain == DOMAIN
    await hass.async_block_till_done()
