"""Tests for the Sonos number platform."""

from contextlib import suppress
from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_MODE,
    ATTR_STEP,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.sonos.const import (
    SONOS_GROUP_VOLUME_REFRESHED,
    SONOS_SPEAKER_ACTIVITY,
    SONOS_STATE_UPDATED,
)
from homeassistant.components.sonos.number import SonosGroupVolumeEntity
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

CROSSOVER_ENTITY = "number.zone_a_sub_crossover_frequency"
GROUP_VOLUME_ENTITY_ID = "number.zone_a_group_volume"


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


async def _setup_numbers_only(async_setup_sonos) -> None:
    """Load only the Number platform (matches Sonos test pattern)."""
    with patch("homeassistant.components.sonos.PLATFORMS", [Platform.NUMBER]):
        await async_setup_sonos()


def _force_grouped(soco) -> str:
    """Make the mock SoCo appear as grouped (>=2 members) with valid attrs; return gid."""
    with suppress(AttributeError):
        # Build or normalize the group
        if getattr(soco, "group", None) is None or isinstance(
            getattr(type(soco), "group", None), PropertyMock
        ):
            grp = MagicMock()
            grp.uid = "G-TEST"
            # Coordinator stub
            coord = MagicMock()
            coord.uid = soco.uid
            grp.coordinator = coord
            # Second member must have uid and is_visible
            member2 = MagicMock()
            member2.uid = "M-TEST"
            member2.is_visible = True
            grp.members = [soco, member2]
            type(soco).group = PropertyMock(return_value=grp)
        else:
            if not getattr(soco.group, "uid", None):
                soco.group.uid = "G-TEST"
            if not getattr(soco.group, "coordinator", None):
                coord = MagicMock()
                coord.uid = soco.uid
                soco.group.coordinator = coord
            member2 = MagicMock()
            member2.uid = "M-TEST"
            member2.is_visible = True
            soco.group.members = [soco, member2]
    return soco.group.uid


async def test_group_volume_sets_backend_and_updates_state(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Setting 33 writes group.volume=33; HA state updates after activity event."""
    # Make it grouped before the platform sets up so subscriptions bind to a real gid
    _force_grouped(soco)
    await _setup_numbers_only(async_setup_sonos)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": GROUP_VOLUME_ENTITY_ID, "value": 33},
        blocking=True,
    )

    assert soco.group.volume == 33

    # State updates on activity (refresh is scheduled -> advance time)
    async_dispatcher_send(hass, SONOS_SPEAKER_ACTIVITY, "test")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    # Verify HA state reflects the new value
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 33


async def test_group_volume_rejects_out_of_range_and_rounds(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Out-of-range rejected; in-range 49.5 rounds to 50."""
    _force_grouped(soco)
    await _setup_numbers_only(async_setup_sonos)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": GROUP_VOLUME_ENTITY_ID, "value": -1},
            blocking=True,
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": GROUP_VOLUME_ENTITY_ID, "value": 101},
            blocking=True,
        )

    # In-range rounding: 49.5 -> round(49.5) == 50
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": GROUP_VOLUME_ENTITY_ID, "value": 49.5},
        blocking=True,
    )
    assert soco.group.volume == 50


async def test_group_volume_updates_on_activity(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Group volume updates when a fresh coordinator value is fanned out."""
    gid = _force_grouped(soco)
    # Ensure the entity subscribes to the same gid we will signal
    with patch.object(SonosGroupVolumeEntity, "_current_group_uid", return_value=gid):
        await _setup_numbers_only(async_setup_sonos)

    # Simulate coordinator fan-out
    soco.group.volume = 55
    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-{gid}", (gid, 55))
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 55


async def test_group_volume_fallback_polling(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Group volume updates when a (simulated) coordinator fan-out occurs."""
    gid = _force_grouped(soco)
    with patch.object(SonosGroupVolumeEntity, "_current_group_uid", return_value=gid):
        await _setup_numbers_only(async_setup_sonos)

    soco.group.volume = 33
    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-{gid}", (gid, 33))
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 33


async def test_group_volume_ungrouped_sets_player_volume(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """When ungrouped, the number mirrors player RenderingControl volume."""
    await _setup_numbers_only(async_setup_sonos)

    # Default fixtures are single-member → ungrouped path
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": GROUP_VOLUME_ENTITY_ID, "value": 27},
        blocking=True,
    )
    assert soco.volume == 27


async def test_group_volume_number_metadata(
    hass: HomeAssistant, async_setup_sonos
) -> None:
    """Group volume number has the expected range, step, and mode."""
    await _setup_numbers_only(async_setup_sonos)
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert GROUP_VOLUME_ENTITY_ID.startswith("number.")
    assert "friendly_name" in state.attributes

    attrs = state.attributes
    assert attrs.get(ATTR_MIN) == 0
    assert attrs.get(ATTR_MAX) == 100
    assert attrs.get(ATTR_STEP) == 1
    assert attrs.get(ATTR_MODE) == "slider"

    # No unit/device_class expected
    assert "unit_of_measurement" not in attrs
    assert "device_class" not in attrs


class _FakeSoCoGroup:
    def __init__(self, uid: str, members=None) -> None:
        self.uid = uid
        self.members = members or ["m1", "m2"]  # grouped (len > 1)


class _FakeSoCo:
    def __init__(self, uid: str, zone_name="Z1", group_uid="G-1") -> None:
        self.uid = uid
        self.zone_name = zone_name
        self.group = _FakeSoCoGroup(group_uid)


class _FakeSpeaker:
    """Minimal speaker stub with attributes used by SonosGroupVolumeEntity."""

    def __init__(self, uid: str, coord_uid: str | None = None, group_uid="G-1") -> None:
        self.uid = uid
        self.zone_name = f"Zone-{uid}"
        self.soco = _FakeSoCo(
            uid=f"SOCO-{uid}", zone_name=self.zone_name, group_uid=group_uid
        )
        self.coordinator = type("C", (), {"uid": coord_uid or uid, "soco": self.soco})
        self.available = True


async def test_group_fanout_unsubscribe_and_resubscribe_on_group_change(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
) -> None:
    """When group uid changes, entity rebinds to the new fanout signal."""
    # Start grouped with G-1 and bring up the platform
    gid1 = _force_grouped(soco)
    if gid1 != "G-1":
        soco.group.uid = "G-1"
        gid1 = "G-1"

    await _setup_numbers_only(async_setup_sonos)

    # Prove we are subscribed to G-1
    soco.group.volume = 11
    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-{gid1}", (gid1, 11))
    await hass.async_block_till_done()
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None and int(float(state.state)) == 11

    # Change the topology: patch SoCo.group to a new object with uid G-2
    member2 = MagicMock()
    member2.uid = "M-TEST"
    member2.is_visible = True

    new_group = MagicMock()
    new_group.uid = "G-2"
    new_group.coordinator = soco.group.coordinator
    new_group.members = [soco, member2]
    new_group.volume = soco.group.volume

    type(soco).group = PropertyMock(return_value=new_group)

    # Trigger the integration to notice the topology change
    async_dispatcher_send(hass, f"{SONOS_STATE_UPDATED}-{soco.uid}")
    await hass.async_block_till_done()

    # Let delayed refresh complete
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    # Send fanout for the new group and ensure the entity updated from it
    new_group.volume = 66
    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-G-2", ("G-2", 66))
    await hass.async_block_till_done()

    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None and int(float(state.state)) == 66

    # Old gid should not alter state anymore
    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-{gid1}", (gid1, 22))
    await hass.async_block_till_done()
    state2 = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state2 is not None and int(float(state2.state)) == 66


async def test_coordinator_listener_rebinds_on_coord_change(
    hass: HomeAssistant,
) -> None:
    """When coordinator uid changes, old coord listener unsubscribes and new one registers."""
    speaker = _FakeSpeaker(uid="S-1", coord_uid="C-OLD", group_uid="G-1")
    entity = SonosGroupVolumeEntity(speaker, MagicMock())
    entity.hass = hass

    coord_unsub_called = False

    def _fake_coord_unsub():
        nonlocal coord_unsub_called
        coord_unsub_called = True

    entity._unsubscribe_coord = _fake_coord_unsub
    entity._coord_uid = "C-OLD"

    seen_signals: list[str] = []

    def _connect(hass_arg, signal, cb):
        # number._rebind_for_topology_change will subscribe to both member and coordinator signals.
        seen_signals.append(signal)

        def _unsub():
            pass

        return _unsub

    with patch(
        "homeassistant.components.sonos.number.async_dispatcher_connect",
        side_effect=_connect,
    ):
        speaker.coordinator.uid = "C-NEW"
        entity._rebind_for_topology_change()

    # Old coord listener was unsubscribed
    assert coord_unsub_called is True

    # New coord listener was registered for the new coordinator uid
    expected = f"{SONOS_STATE_UPDATED}-C-NEW"
    assert expected in seen_signals, (
        f"Expected to subscribe to {expected}, saw {seen_signals}"
    )

    # Sanity check: member subscription likely present too
    assert f"{SONOS_STATE_UPDATED}-S-1" in seen_signals
    assert entity._coord_uid == "C-NEW"
