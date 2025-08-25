"""Tests for the Sonos number platform."""

from contextlib import suppress
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.components.sonos.const import SONOS_SPEAKER_ACTIVITY
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

CROSSOVER_ENTITY = "number.zone_a_sub_crossover_frequency"


async def test_number_entities(
    hass: HomeAssistant, async_autosetup_sonos, soco, entity_registry: er.EntityRegistry
) -> None:
    """Test number entities."""
    balance_number = entity_registry.entities["number.zone_a_balance"]
    balance_state = hass.states.get(balance_number.entity_id)
    assert balance_state.state == "39"

    bass_number = entity_registry.entities["number.zone_a_bass"]
    bass_state = hass.states.get(bass_number.entity_id)
    assert bass_state.state == "1"

    treble_number = entity_registry.entities["number.zone_a_treble"]
    treble_state = hass.states.get(treble_number.entity_id)
    assert treble_state.state == "-1"

    audio_delay_number = entity_registry.entities["number.zone_a_audio_delay"]
    audio_delay_state = hass.states.get(audio_delay_number.entity_id)
    assert audio_delay_state.state == "2"

    surround_level_number = entity_registry.entities["number.zone_a_surround_level"]
    surround_level_state = hass.states.get(surround_level_number.entity_id)
    assert surround_level_state.state == "3"

    music_surround_level_number = entity_registry.entities[
        "number.zone_a_music_surround_level"
    ]
    music_surround_level_state = hass.states.get(music_surround_level_number.entity_id)
    assert music_surround_level_state.state == "4"

    with patch.object(
        type(soco), "audio_delay", new_callable=PropertyMock
    ) as mock_audio_delay:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: audio_delay_number.entity_id, "value": 3},
            blocking=True,
        )
        mock_audio_delay.assert_called_once_with(3)

    sub_gain_number = entity_registry.entities["number.zone_a_sub_gain"]
    sub_gain_state = hass.states.get(sub_gain_number.entity_id)
    assert sub_gain_state.state == "5"

    with patch.object(
        type(soco), "sub_gain", new_callable=PropertyMock
    ) as mock_sub_gain:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: sub_gain_number.entity_id, "value": -8},
            blocking=True,
        )
        mock_sub_gain.assert_called_once_with(-8)

    # sub_crossover is only available on Sonos Amp devices, see test_amp_number_entities
    assert CROSSOVER_ENTITY not in entity_registry.entities


async def test_amp_number_entities(
    hass: HomeAssistant, async_setup_sonos, soco, entity_registry: er.EntityRegistry
) -> None:
    """Test the sub_crossover feature only available on Sonos Amp devices.

    The sub_crossover value will be None on all other device types.
    """
    with patch.object(soco, "sub_crossover", 50):
        await async_setup_sonos()

    sub_crossover_number = entity_registry.entities[CROSSOVER_ENTITY]
    sub_crossover_state = hass.states.get(sub_crossover_number.entity_id)
    assert sub_crossover_state.state == "50"

    with patch.object(
        type(soco), "sub_crossover", new_callable=PropertyMock
    ) as mock_sub_crossover:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: sub_crossover_number.entity_id, "value": 110},
            blocking=True,
        )
        mock_sub_crossover.assert_called_once_with(110)


# ─────────────────────────────────────────────
# Appended group-volume tests
# ─────────────────────────────────────────────


async def _setup_numbers_only(async_setup_sonos) -> None:
    """Load only the Number platform (matches Sonos test pattern)."""
    with patch("homeassistant.components.sonos.PLATFORMS", [Platform.NUMBER]):
        await async_setup_sonos()


def _expected_group_volume_entity_id() -> str:
    """The translated entity_id for group volume (zone_a fixture)."""
    return "number.zone_a_group_volume"


def _force_grouped(soco) -> None:
    """Make the mock SoCo appear as part of a group (>=2 members)."""
    # The default test fixture has a single-member group; make it look grouped
    # so number.py takes the GroupRenderingControl path.
    with suppress(AttributeError):
        soco.group.members = [soco, object()]


async def test_group_volume_entity_created(
    hass: HomeAssistant, async_setup_sonos, entity_registry: er.EntityRegistry
) -> None:
    """The group volume number entity should be created with translated id."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    # Confirm entity exists via registry and state machine (translation applied)
    assert entity_registry.async_get(group_eid) is not None
    state = hass.states.get(group_eid)
    assert state is not None, "Expected a Sonos group volume number entity"
    assert group_eid.startswith("number.")
    assert "friendly_name" in state.attributes


async def test_group_volume_sets_backend_and_updates_state(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Setting 33 writes group.volume=33; HA state updates after activity event."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    _force_grouped(soco)

    # Call number.set_value on the entity (native range is 0–100)
    await hass.services.async_call(
        "number", "set_value", {"entity_id": group_eid, "value": 33}, blocking=True
    )

    # Backend write
    assert soco.group.volume == 33

    # State updates on activity
    async_dispatcher_send(hass, SONOS_SPEAKER_ACTIVITY, "test")
    await hass.async_block_till_done()

    state = hass.states.get(group_eid)
    assert state is not None
    # entity returns float(self._value), HA may render "33" or "33.0" → normalize
    assert int(float(state.state)) == 33


async def test_group_volume_rejects_out_of_range_and_rounds(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Out-of-range rejected; in-range 49.5 rounds to 50."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    _force_grouped(soco)

    # Out-of-range inputs are rejected by HA before entity method runs
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": group_eid, "value": -1}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number", "set_value", {"entity_id": group_eid, "value": 101}, blocking=True
        )

    # In-range rounding: 49.5 -> round(49.5) == 50
    await hass.services.async_call(
        "number", "set_value", {"entity_id": group_eid, "value": 49.5}, blocking=True
    )
    assert soco.group.volume == 50


async def test_group_volume_updates_on_activity(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Group volume updates when an activity event is processed."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    _force_grouped(soco)

    # Change the underlying (0–100) group volume and simulate activity
    soco.group.volume = 55
    async_dispatcher_send(hass, SONOS_SPEAKER_ACTIVITY, "test")
    await hass.async_block_till_done()

    state = hass.states.get(group_eid)
    assert state is not None
    assert int(float(state.state)) == 55


async def test_group_volume_fallback_polling(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Group volume updates via on-demand read if no subscription events arrive."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    _force_grouped(soco)

    # Simulate a global activity event; entity reads native value
    soco.group.volume = 33
    async_dispatcher_send(hass, SONOS_SPEAKER_ACTIVITY, "test")
    await hass.async_block_till_done()

    state = hass.states.get(group_eid)
    assert state is not None
    assert int(float(state.state)) == 33


async def test_group_volume_ungrouped_sets_player_volume(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """When ungrouped, the number mirrors player RenderingControl volume."""
    await _setup_numbers_only(async_setup_sonos)
    group_eid = _expected_group_volume_entity_id()

    # Default fixtures are single-member → ungrouped path
    await hass.services.async_call(
        "number", "set_value", {"entity_id": group_eid, "value": 27}, blocking=True
    )
    assert soco.volume == 27


async def test_group_volume_number_metadata(
    hass: HomeAssistant, async_setup_sonos
) -> None:
    """Group volume number has the expected range, step, and mode."""
    await _setup_numbers_only(async_setup_sonos)
    eid = _expected_group_volume_entity_id()
    state = hass.states.get(eid)
    assert state is not None

    attrs = state.attributes
    # Range 0–100 with step 1 and slider mode
    assert attrs.get("min") == 0
    assert attrs.get("max") == 100
    assert attrs.get("step") == 1
    assert attrs.get("mode") == "slider"

    # No unit/device_class expected
    assert "unit_of_measurement" not in attrs
    assert "device_class" not in attrs
