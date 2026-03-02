"""Tests for the Sonos number platform."""

from contextlib import suppress
from unittest.mock import MagicMock, PropertyMock, patch

from soco.exceptions import SoCoException

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.components.sonos.const import (
    SONOS_SPEAKER_ACTIVITY,
    SONOS_STATE_UPDATED,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import MockSoCo

from tests.common import SnapshotAssertion

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


def _force_grouped(soco: MockSoCo, *, coordinator_uid: str | None = None) -> str:
    """Make the mock SoCo appear as grouped (>=2 members) with valid attrs; return gid.

    coordinator_uid:
      - None/default: coordinator is this soco (normal "coordinator" case)
      - non-matching uid: coordinator is another visible member with that uid
    """
    with suppress(AttributeError):
        coord_uid = soco.uid if coordinator_uid is None else coordinator_uid

        # Build or normalize the group object
        if getattr(soco, "group", None) is None or isinstance(
            getattr(type(soco), "group", None), PropertyMock
        ):
            grp = MagicMock()
            grp.uid = "G-TEST"

            member2 = MagicMock()
            member2.uid = "M-TEST" if coord_uid == soco.uid else coord_uid
            member2.is_visible = True

            grp.coordinator = soco if coord_uid == soco.uid else member2
            grp.members = [soco, member2]
            type(soco).group = PropertyMock(return_value=grp)
        else:
            if not getattr(soco.group, "uid", None):
                soco.group.uid = "G-TEST"

            member2 = MagicMock()
            member2.uid = "M-TEST" if coord_uid == soco.uid else coord_uid
            member2.is_visible = True
            soco.group.members = [soco, member2]
            soco.group.coordinator = soco if coord_uid == soco.uid else member2

    return soco.group.uid


async def _refresh_group_volume_entity(hass: HomeAssistant) -> None:
    """Force the group-volume entity to refresh via HA's update pipeline."""
    await async_update_entity(hass, GROUP_VOLUME_ENTITY_ID)
    await hass.async_block_till_done()


async def test_group_volume_sets_backend_and_updates_state(
    hass: HomeAssistant, async_setup_sonos, soco: MockSoCo
) -> None:
    """Setting 33 writes group.volume=33; HA state updates after refresh."""
    _force_grouped(soco)
    await _setup_numbers_only(async_setup_sonos)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: GROUP_VOLUME_ENTITY_ID, "value": 33},
        blocking=True,
    )
    assert soco.group.volume == 33

    async_dispatcher_send(hass, SONOS_SPEAKER_ACTIVITY, "test")
    await hass.async_block_till_done()
    await _refresh_group_volume_entity(hass)

    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 33


async def test_group_volume_rounds_in_range(
    hass: HomeAssistant, async_setup_sonos, soco: MockSoCo
) -> None:
    """In-range 49.5 rounds to 50."""
    _force_grouped(soco)
    await _setup_numbers_only(async_setup_sonos)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: GROUP_VOLUME_ENTITY_ID, "value": 49.5},
        blocking=True,
    )
    assert soco.group.volume == 50


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
    hass: HomeAssistant, async_setup_sonos, soco: MockSoCo
) -> None:
    """Tests handling of SoCoException when reading group volume."""
    _force_grouped(soco)

    with patch.object(
        type(soco.group), "volume", new_callable=PropertyMock
    ) as mock_volume:
        mock_volume.side_effect = SoCoException("Boom!")

        await _setup_numbers_only(async_setup_sonos)

        await _refresh_group_volume_entity(hass)

        state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
        assert state is not None
        assert state.state == STATE_UNKNOWN


async def test_group_volume_refreshes_on_topology_change(
    hass: HomeAssistant, async_setup_sonos, soco: MockSoCo
) -> None:
    """Verify group volume updates when group object/volume changes."""
    member2 = MagicMock()
    member2.uid = "M-2"
    member2.is_visible = True

    initial_group = MagicMock()
    initial_group.uid = "G-1"
    initial_group.coordinator = soco
    initial_group.members = [soco, member2]
    initial_group.volume = 15
    type(soco).group = PropertyMock(return_value=initial_group)

    await _setup_numbers_only(async_setup_sonos)

    await _refresh_group_volume_entity(hass)

    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 15

    new_group = MagicMock()
    new_group.uid = "G-99"
    new_group.coordinator = soco
    new_group.members = [soco, member2]
    new_group.volume = 42
    type(soco).group = PropertyMock(return_value=new_group)

    async_dispatcher_send(hass, f"{SONOS_STATE_UPDATED}-{soco.uid}")
    await hass.async_block_till_done()
    await _refresh_group_volume_entity(hass)

    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 42


async def test_group_volume_set_value_soco_exception_on_group_read(
    hass: HomeAssistant, async_setup_sonos, soco: MockSoCo
) -> None:
    """SoCoException while determining grouping aborts the write gracefully."""
    _force_grouped(soco)
    await _setup_numbers_only(async_setup_sonos)

    type(soco).group = PropertyMock(side_effect=SoCoException("group read error"))

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: GROUP_VOLUME_ENTITY_ID, "value": 50},
        blocking=True,
    )
