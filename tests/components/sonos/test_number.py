"""Tests for the Sonos number platform."""

from datetime import timedelta
from unittest.mock import PropertyMock, patch

import pytest
from soco.exceptions import SoCoException

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import MockSoCo, SoCoMockFactory, group_speakers, ungroup_speakers

from tests.common import SnapshotAssertion, async_fire_time_changed

CROSSOVER_ENTITY = "number.zone_a_sub_crossover_frequency"
GROUP_VOLUME_ENTITY_ID = "number.zone_a_group_volume"


async def test_number_entities(
    hass: HomeAssistant,
    async_autosetup_sonos,
    soco: MockSoCo,
    entity_registry: er.EntityRegistry,
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
    hass: HomeAssistant,
    async_setup_sonos,
    soco: MockSoCo,
    entity_registry: er.EntityRegistry,
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


async def _setup_numbers_only(async_setup_sonos) -> None:
    """Load only the Number platform (matches Sonos test pattern)."""
    with patch("homeassistant.components.sonos.PLATFORMS", [Platform.NUMBER]):
        await async_setup_sonos()


async def test_group_volume_sets_backend_and_updates_state(
    hass: HomeAssistant,
    async_setup_two_sonos_speakers,
    soco_factory: SoCoMockFactory,
) -> None:
    """Setting 33 writes group.volume=33; HA state updates after write completes."""
    await async_setup_two_sonos_speakers()
    soco_lr = soco_factory.mock_list["10.10.10.1"]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.living_room_group_volume", "value": 33},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()

    assert soco_lr.group.volume == 33

    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert int(float(state.state)) == 33


async def test_group_volume_rounds_in_range(
    hass: HomeAssistant,
    async_setup_two_sonos_speakers,
    soco_factory: SoCoMockFactory,
) -> None:
    """In-range 49.5 rounds to 50."""
    await async_setup_two_sonos_speakers()
    soco_lr = soco_factory.mock_list["10.10.10.1"]

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.living_room_group_volume", "value": 49.5},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()

    assert soco_lr.group.volume == 50


async def test_group_volume_ungrouped_sets_player_volume(
    hass: HomeAssistant, async_setup_sonos, soco: MockSoCo
) -> None:
    """When ungrouped, the number mirrors player RenderingControl volume."""
    await _setup_numbers_only(async_setup_sonos)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: GROUP_VOLUME_ENTITY_ID, "value": 27},
        blocking=True,
    )
    assert soco.volume == 27


async def test_group_volume_number_metadata(
    hass: HomeAssistant,
    async_setup_sonos,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test basic state and attributes (snapshot)."""
    await _setup_numbers_only(async_setup_sonos)

    entity_entry = entity_registry.async_get(GROUP_VOLUME_ENTITY_ID)
    assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")

    state = hass.states.get(entity_entry.entity_id)
    assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_group_volume_exception(
    hass: HomeAssistant,
    async_setup_two_sonos_speakers,
    soco_factory: SoCoMockFactory,
) -> None:
    """SoCoException on grouped volume read during setup results in STATE_UNKNOWN."""
    soco_lr = soco_factory.mock_list["10.10.10.1"]

    with patch.object(
        type(soco_lr.group), "volume", new_callable=PropertyMock
    ) as mock_volume:
        mock_volume.side_effect = SoCoException("Boom!")
        await async_setup_two_sonos_speakers()
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.async_block_till_done()

    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_group_volume_transitions_to_unknown_after_good_read(
    hass: HomeAssistant,
    async_setup_two_sonos_speakers,
    soco_factory: SoCoMockFactory,
) -> None:
    """State transitions to STATE_UNKNOWN when volume read fails after a successful read."""
    soco_lr = soco_factory.mock_list["10.10.10.1"]
    soco_br = soco_factory.mock_list["10.10.10.2"]
    soco_lr.group.volume = 20

    await async_setup_two_sonos_speakers()

    # Establish a known good state first.
    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert int(float(state.state)) == 20

    # Now make group.volume raise on every subsequent read; topology change
    # triggers a fresh _async_update_group_volume which should clear the cached value.
    with patch.object(
        type(soco_lr.group), "volume", new_callable=PropertyMock
    ) as mock_volume:
        mock_volume.side_effect = SoCoException("Boom!")
        ungroup_speakers(soco_lr, soco_br)
        group_speakers(soco_lr, soco_br)
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.async_block_till_done()

    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_group_volume_refreshes_on_topology_change(
    hass: HomeAssistant,
    async_setup_two_sonos_speakers,
    soco_factory: SoCoMockFactory,
) -> None:
    """Verify group volume re-reads after a topology change (ungroup + regroup)."""
    soco_lr = soco_factory.mock_list["10.10.10.1"]
    soco_br = soco_factory.mock_list["10.10.10.2"]
    soco_lr.group.volume = 15

    await async_setup_two_sonos_speakers()

    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert int(float(state.state)) == 15

    soco_lr.group.volume = 42
    ungroup_speakers(soco_lr, soco_br)
    group_speakers(soco_lr, soco_br)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()

    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert int(float(state.state)) == 42


async def test_group_volume_set_value_soco_exception_on_group_write(
    hass: HomeAssistant,
    async_setup_two_sonos_speakers,
    soco_factory: SoCoMockFactory,
) -> None:
    """SoCoException during grouped write raises HomeAssistantError; player volume unchanged."""
    await async_setup_two_sonos_speakers()
    soco_lr = soco_factory.mock_list["10.10.10.1"]
    initial_volume = soco_lr.volume

    with patch.object(
        type(soco_lr.group), "volume", new_callable=PropertyMock
    ) as group_vol_mock:
        group_vol_mock.side_effect = SoCoException("group write error")
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: "number.living_room_group_volume", "value": 50},
                blocking=True,
            )

    # Player volume must not have been modified — the write targeted group.volume,
    # not the individual player, and raising on that path must not fall back to soco.volume.
    assert soco_lr.volume == initial_volume


async def test_group_volume_shows_player_volume_after_ungroup(
    hass: HomeAssistant,
    async_setup_two_sonos_speakers,
    soco_factory: SoCoMockFactory,
) -> None:
    """After ungrouping, group volume transitions to the solo player volume, not unknown."""
    soco_lr = soco_factory.mock_list["10.10.10.1"]
    soco_br = soco_factory.mock_list["10.10.10.2"]
    soco_lr.group.volume = 25

    await async_setup_two_sonos_speakers()

    # Confirm initial grouped state is visible.
    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert int(float(state.state)) == 25

    ungroup_speakers(soco_lr, soco_br)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()

    # Advance time past the 0.5 s _do_update debounce to trigger the refresh.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.async_block_till_done()

    # After ungrouping the solo player's volume is the source of truth.
    state = hass.states.get("number.living_room_group_volume")
    assert state is not None
    assert int(float(state.state)) == soco_lr.volume
