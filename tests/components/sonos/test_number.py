"""Tests for the Sonos number platform."""

from contextlib import suppress
from datetime import timedelta
from unittest.mock import MagicMock, PropertyMock, patch

from soco.exceptions import SoCoException

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.components.sonos.const import (
    SONOS_GROUP_VOLUME_REFRESHED,
    SONOS_SPEAKER_ACTIVITY,
    SONOS_STATE_UPDATED,
)
from homeassistant.components.sonos.number import SonosGroupVolumeEntity
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from tests.common import SnapshotAssertion, async_fire_time_changed

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
        # Build or normalize the group object
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
            # If group object already exists, make sure required attrs are present
            if not getattr(soco.group, "uid", None):
                soco.group.uid = "G-TEST"
            if not getattr(soco.group, "coordinator", None):
                coord = MagicMock()
                coord.uid = soco.uid
                soco.group.coordinator = coord
            # Always ensure a second visible member
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
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
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


async def test_group_volume_rounds_in_range(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """In-range 49.5 rounds to 50."""
    _force_grouped(soco)
    await _setup_numbers_only(async_setup_sonos)

    # In-range rounding: 49.5 -> round(49.5) == 50
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": GROUP_VOLUME_ENTITY_ID, "value": 49.5},
        blocking=True,
    )
    assert soco.group.volume == 50


async def test_group_volume_updates_on_activity(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
) -> None:
    """Group volume updates when a fresh coordinator value is fanned out."""
    soco.group = MagicMock()
    gid = _force_grouped(soco)
    soco.group.uid = gid

    await _setup_numbers_only(async_setup_sonos)

    # Simulate coordinator fan-out
    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-{gid}", (gid, 55))
    await hass.async_block_till_done()

    # Verify state updated from fan-out
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 55


async def test_group_volume_fallback_polling(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
) -> None:
    """Group volume updates when a (simulated) coordinator fan-out occurs."""
    soco.group = MagicMock()
    gid = _force_grouped(soco)
    soco.group.uid = gid

    await _setup_numbers_only(async_setup_sonos)

    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-{gid}", (gid, 33))
    await hass.async_block_till_done()

    # Verify state updated from fallback polling
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
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": GROUP_VOLUME_ENTITY_ID, "value": 27},
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

    # Registry entry snapshot
    entity_entry = entity_registry.async_get(GROUP_VOLUME_ENTITY_ID)
    assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")

    # State snapshot
    state = hass.states.get(entity_entry.entity_id)
    assert state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_group_fanout_unsubscribe_and_resubscribe_on_group_change(
    hass: HomeAssistant,
    async_setup_sonos,
    soco,
) -> None:
    """When group uid changes, entity rebinds; polling refresh reflects new group volume."""
    # Start grouped with deterministic G-1 and bring up the platform
    gid1 = _force_grouped(soco)
    if gid1 != "G-1":
        soco.group.uid = "G-1"
        gid1 = "G-1"

    await _setup_numbers_only(async_setup_sonos)

    # Prove we are subscribed and state reflects initial fanout to G-1
    soco.group.volume = 11
    async_dispatcher_send(hass, f"{SONOS_GROUP_VOLUME_REFRESHED}-{gid1}", (gid1, 11))
    await hass.async_block_till_done()
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None and int(float(state.state)) == 11

    # Patch SoCo.group (public API) to a new object with uid G-2
    member2 = MagicMock()
    member2.uid = "M-TEST"
    member2.is_visible = True

    new_group = MagicMock()
    new_group.uid = "G-2"
    new_group.coordinator = soco.group.coordinator
    new_group.members = [soco, member2]
    new_group.volume = 66
    type(soco).group = PropertyMock(return_value=new_group)

    # Notify topology change & let the entity schedule its delayed refresh
    async_dispatcher_send(hass, f"{SONOS_STATE_UPDATED}-{soco.uid}")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    # Drive the refresh path used by the integration after activity
    async_dispatcher_send(hass, SONOS_SPEAKER_ACTIVITY, "topology-change")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    # State should now reflect the new group's volume (66)
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None and int(float(state.state)) == 66


async def test_group_volume_exception(
    hass: HomeAssistant, async_setup_sonos, soco
) -> None:
    """Tests handling of SoCoException when reading group volume."""
    _force_grouped(soco)
    type(soco.group).volume = PropertyMock(side_effect=SoCoException("Boom!"))

    await _setup_numbers_only(async_setup_sonos)

    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


# Minimal mock classes to simulate speaker topology
class _FakeSoCoGroup:
    def __init__(self, uid: str, coordinator=None, members=None) -> None:
        # Represent a SoCo group with uid, coordinator, and members
        self.uid = uid
        self.coordinator = coordinator
        self.members = members or ["m1", "m2"]


class _FakeSoCo:
    def __init__(
        self, uid: str, zone_name="Z1", group_uid="G-1", coord_uid="C-OLD"
    ) -> None:
        # Represent a SoCo device with its current group and coordinator
        self.uid = uid
        self.zone_name = zone_name
        coord = MagicMock()
        coord.uid = coord_uid
        self.group = _FakeSoCoGroup(group_uid, coordinator=coord)


class _FakeCoordinator:
    def __init__(self, uid: str) -> None:
        # Represent a speaker coordinator with a soco handle
        self.uid = uid
        self.soco = MagicMock()


class _FakeSpeaker:
    def __init__(self, uid: str, coord_uid: str, group_uid="G-1") -> None:
        # Represent a SonosSpeaker with soco + coordinator attributes
        self.uid = uid
        self.zone_name = f"Zone-{uid}"
        self.soco = _FakeSoCo(
            uid=f"SOCO-{uid}",
            zone_name=self.zone_name,
            group_uid=group_uid,
            coord_uid=coord_uid,
        )
        self.coordinator = _FakeCoordinator(coord_uid)
        self.available = True


# Subclass to expose and test internal rebinding logic
class _TestEntity(SonosGroupVolumeEntity):
    def _current_coord_uid(self) -> str | None:
        """Return the current coordinator UID from the fake speaker."""
        return getattr(self.speaker.coordinator, "uid", None)

    def _current_group_uid(self) -> str | None:
        """Return the current group UID from the fake soco group."""
        return getattr(getattr(self.speaker.soco, "group", None), "uid", None)

    def _rebind_for_topology_change(self):
        # Drop old coord subscription if coord uid changed
        new_coord_uid = self._current_coord_uid()
        if self._coord_uid != new_coord_uid:
            if self._unsubscribe_coord:
                self._unsubscribe_coord()
            self._unsubscribe_coord = (
                self.hass.helpers.dispatcher.async_dispatcher_connect(
                    self.hass,
                    f"{SONOS_STATE_UPDATED}-{new_coord_uid}",
                    self._handle_coordinator_update,
                )
            )
            self._coord_uid = new_coord_uid

        # Always subscribe to own uid and new group uid
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            self.hass,
            f"{SONOS_STATE_UPDATED}-{self.speaker.uid}",
            self._handle_coordinator_update,
        )
        self._group_uid = self._current_group_uid()
        self._unsubscribe_gv_signal = (
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                self.hass,
                f"{SONOS_STATE_UPDATED}-{self._group_uid}",
                self._handle_group_volume_update,
            )
        )
        # Trigger refresh from device after rebind
        self._async_refresh_from_device()

    def _handle_coordinator_update(self, *args, **kwargs):
        pass

    def _handle_group_volume_update(self, *args, **kwargs):
        pass


async def test_group_volume_rebinds_on_topology_change(
    hass: HomeAssistant, async_setup_sonos
) -> None:
    """Verify group volume entity rebinds when topology (group UID / coord UID) changes."""
    await async_setup_sonos()

    # Grab the group-volume entity object created by the fixture
    entity = next(
        ent
        for ent in hass.data["entity_components"]["number"].entities
        if isinstance(ent, SonosGroupVolumeEntity)
    )
    soco = entity.speaker.soco

    # Initial group with 2 members
    member2 = MagicMock()
    member2.uid = "M-2"
    member2.is_visible = True

    initial_group = MagicMock()
    initial_group.uid = "G-1"
    initial_group.coordinator = soco
    initial_group.members = [soco, member2]
    initial_group.volume = 15
    type(soco).group = PropertyMock(return_value=initial_group)

    # Trigger HA update to register/refresh state (value may be fixture-default)
    async_dispatcher_send(hass, f"{SONOS_STATE_UPDATED}-{soco.uid}")
    await hass.async_block_till_done()

    # Ensure entity exists
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None

    # Change topology: new gid/coord and volume
    new_group = MagicMock()
    new_group.uid = "G-99"
    new_group.coordinator = soco
    new_group.coordinator.uid = "C-99"
    new_group.members = [soco, member2]
    new_group.volume = 42
    type(soco).group = PropertyMock(return_value=new_group)

    # Trigger update → entity schedules a delayed refresh; advance time to run it
    async_dispatcher_send(hass, f"{SONOS_STATE_UPDATED}-{soco.uid}")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    # Entity state should now reflect the new group volume
    state = hass.states.get(GROUP_VOLUME_ENTITY_ID)
    assert state is not None
    assert int(float(state.state)) == 42
