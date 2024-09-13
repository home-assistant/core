"""The tests for the Ring number platform."""

from unittest.mock import Mock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


@pytest.mark.parametrize(
    ("entity_id", "unique_id"),
    [
        ("number.downstairs_volume", "123456-volume"),
        ("number.front_door_volume", "987654-volume"),
        ("number.ingress_doorbell_volume", "185036587-doorbell_volume"),
        ("number.ingress_mic_volume", "185036587-mic_volume"),
        ("number.ingress_voice_volume", "185036587-voice_volume"),
    ],
)
async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_ring_client: Mock,
    entity_id: str,
    unique_id: str,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, Platform.NUMBER)

    entry = entity_registry.async_get(entity_id)
    assert entry is not None and entry.unique_id == unique_id


@pytest.mark.parametrize(
    ("entity_id", "initial_state"),
    [
        ("number.downstairs_volume", "2.0"),
        ("number.front_door_volume", "1.0"),
        ("number.ingress_doorbell_volume", "8.0"),
        ("number.ingress_mic_volume", "11.0"),
        ("number.ingress_voice_volume", "11.0"),
    ],
)
async def test_initial_state(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    entity_id: str,
    initial_state: str,
) -> None:
    """Tests that the initial state of a device is correct."""
    await setup_platform(hass, Platform.NUMBER)

    state = hass.states.get(entity_id)
    assert state is not None and state.state == initial_state


@pytest.mark.parametrize(
    ("entity_id", "new_value"),
    [
        ("number.downstairs_volume", "4.0"),
        ("number.front_door_volume", "3.0"),
        ("number.ingress_doorbell_volume", "7.0"),
        ("number.ingress_mic_volume", "2.0"),
        ("number.ingress_voice_volume", "5.0"),
    ],
)
async def test_volume_can_be_changed(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    entity_id: str,
    new_value: str,
) -> None:
    """Tests the volume can be changed correctly."""
    await setup_platform(hass, Platform.NUMBER)

    state = hass.states.get(entity_id)
    assert state is not None
    old_value = state.state

    # otherwise this test would be pointless
    assert old_value != new_value

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_id, "value": new_value},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None and state.state == new_value
