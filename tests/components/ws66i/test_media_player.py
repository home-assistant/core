"""The tests for WS66i Media player platform."""
from collections import defaultdict
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
)
from homeassistant.components.ws66i.const import (
    CONF_SOURCES,
    DOMAIN,
    INIT_OPTIONS_DEFAULT,
    MAX_VOL,
    POLL_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_IP_ADDRESS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_SOURCE_DIC = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
}
MOCK_CONFIG = {CONF_IP_ADDRESS: "fake ip"}
MOCK_OPTIONS = {CONF_SOURCES: MOCK_SOURCE_DIC}
MOCK_DEFAULT_OPTIONS = {CONF_SOURCES: INIT_OPTIONS_DEFAULT}

ZONE_1_ID = "media_player.zone_11"
ZONE_2_ID = "media_player.zone_12"
ZONE_7_ID = "media_player.zone_21"


class AttrDict(dict):
    """Helper class for mocking attributes."""

    def __setattr__(self, name, value):
        """Set attribute."""
        self[name] = value

    def __getattr__(self, item):
        """Get attribute."""
        try:
            return self[item]
        except KeyError as err:
            # The reason for doing this is because of the deepcopy in my code
            raise AttributeError(item) from err


class MockWs66i:
    """Mock for pyws66i object."""

    def __init__(self, fail_open=False, fail_zone_check=None):
        """Init mock object."""
        self.zones = defaultdict(
            lambda: AttrDict(
                power=True, volume=0, mute=True, source=1, treble=0, bass=0, balance=10
            )
        )
        self.fail_open = fail_open
        self.fail_zone_check = fail_zone_check

    def open(self):
        """Open socket. Do nothing."""
        if self.fail_open is True:
            raise ConnectionError()

    def close(self):
        """Close socket. Do nothing."""

    def zone_status(self, zone_id):
        """Get zone status."""
        if self.fail_zone_check is not None and zone_id in self.fail_zone_check:
            return None
        status = self.zones[zone_id]
        status.zone = zone_id
        return AttrDict(status)

    def set_source(self, zone_id, source_idx):
        """Set source for zone."""
        self.zones[zone_id].source = source_idx

    def set_power(self, zone_id, power):
        """Turn zone on/off."""
        self.zones[zone_id].power = power

    def set_mute(self, zone_id, mute):
        """Mute/unmute zone."""
        self.zones[zone_id].mute = mute

    def set_volume(self, zone_id, volume):
        """Set volume for zone."""
        self.zones[zone_id].volume = volume

    def restore_zone(self, zone):
        """Restore zone status."""
        self.zones[zone.zone] = AttrDict(zone)


async def test_setup_success(hass: HomeAssistant) -> None:
    """Test connection success."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: MockWs66i(),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ZONE_1_ID) is not None


async def _setup_ws66i(hass, ws66i) -> MockConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_DEFAULT_OPTIONS
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: ws66i,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def _setup_ws66i_with_options(hass, ws66i) -> MockConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: ws66i,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def _call_media_player_service(hass, name, data):
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, name, service_data=data, blocking=True
    )


async def test_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test updating values from ws66i."""
    ws66i = MockWs66i()
    _ = await _setup_ws66i_with_options(hass, ws66i)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    ws66i.set_source(11, 3)
    ws66i.set_volume(11, MAX_VOL)

    with patch.object(MockWs66i, "open") as method_call:
        freezer.tick(POLL_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert not method_call.called

    state = hass.states.get(ZONE_1_ID)

    assert hass.states.is_state(ZONE_1_ID, STATE_ON)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"


async def test_failed_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test updating failure from ws66i."""
    ws66i = MockWs66i()
    _ = await _setup_ws66i_with_options(hass, ws66i)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    ws66i.set_source(11, 3)
    ws66i.set_volume(11, MAX_VOL)

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Failed update, close called
    with patch.object(MockWs66i, "zone_status", return_value=None):
        freezer.tick(POLL_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_1_ID, STATE_UNAVAILABLE)

    # A connection re-attempt fails
    with patch.object(MockWs66i, "zone_status", return_value=None):
        freezer.tick(POLL_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    # A connection re-attempt succeeds
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # confirm entity is back on
    state = hass.states.get(ZONE_1_ID)

    assert hass.states.is_state(ZONE_1_ID, STATE_ON)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"


async def test_supported_features(hass: HomeAssistant) -> None:
    """Test supported features property."""
    await _setup_ws66i(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    assert (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        == state.attributes["supported_features"]
    )


async def test_source_list(hass: HomeAssistant) -> None:
    """Test source list property."""
    await _setup_ws66i(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    # Note, the list is sorted!
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == list(
        INIT_OPTIONS_DEFAULT.values()
    )


async def test_source_list_with_options(hass: HomeAssistant) -> None:
    """Test source list property."""
    await _setup_ws66i_with_options(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    # Note, the list is sorted!
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == list(MOCK_SOURCE_DIC.values())


async def test_select_source(hass: HomeAssistant) -> None:
    """Test source selection methods."""
    ws66i = MockWs66i()
    await _setup_ws66i_with_options(hass, ws66i)

    await _call_media_player_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {"entity_id": ZONE_1_ID, ATTR_INPUT_SOURCE: "three"},
    )
    assert ws66i.zones[11].source == 3


async def test_source_select(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test source selection simulated from keypad."""
    ws66i = MockWs66i()
    _ = await _setup_ws66i_with_options(hass, ws66i)

    ws66i.set_source(11, 5)

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes.get(ATTR_INPUT_SOURCE) == "five"


async def test_turn_on_off(hass: HomeAssistant) -> None:
    """Test turning on the zone."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(hass, SERVICE_TURN_OFF, {"entity_id": ZONE_1_ID})
    assert not ws66i.zones[11].power

    await _call_media_player_service(hass, SERVICE_TURN_ON, {"entity_id": ZONE_1_ID})
    assert ws66i.zones[11].power


async def test_mute_volume(hass: HomeAssistant) -> None:
    """Test mute functionality."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.5}
    )
    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": False}
    )
    assert not ws66i.zones[11].mute

    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": True}
    )
    assert ws66i.zones[11].mute


async def test_volume_up_down(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test increasing volume by one."""
    ws66i = MockWs66i()
    _ = await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    assert ws66i.zones[11].volume == 0

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # should not go below zero
    assert ws66i.zones[11].volume == 0

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert ws66i.zones[11].volume == 1

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert ws66i.zones[11].volume == MAX_VOL

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})

    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # should not go above 38 (MAX_VOL)
    assert ws66i.zones[11].volume == MAX_VOL

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    assert ws66i.zones[11].volume == MAX_VOL - 1


async def test_volume_while_mute(hass: HomeAssistant) -> None:
    """Test increasing volume by one."""
    ws66i = MockWs66i()
    _ = await _setup_ws66i(hass, ws66i)

    # Set vol to a known value
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    assert ws66i.zones[11].volume == 0

    # Set mute to a known value, False
    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": False}
    )
    assert not ws66i.zones[11].mute

    # Mute the zone
    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": True}
    )
    assert ws66i.zones[11].mute

    # Increase volume. Mute state should go back to unmutted
    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})
    assert ws66i.zones[11].volume == 1
    assert not ws66i.zones[11].mute

    # Mute the zone again
    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": True}
    )
    assert ws66i.zones[11].mute

    # Decrease volume. Mute state should go back to unmutted
    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    assert ws66i.zones[11].volume == 0
    assert not ws66i.zones[11].mute

    # Mute the zone again
    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": True}
    )
    assert ws66i.zones[11].mute

    # Set to max volume. Mute state should go back to unmutted
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    assert ws66i.zones[11].volume == MAX_VOL
    assert not ws66i.zones[11].mute


async def test_first_run_with_available_zones(hass: HomeAssistant) -> None:
    """Test first run with all zones available."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_7_ID)
    assert not entry.disabled


async def test_first_run_with_failing_zones(hass: HomeAssistant) -> None:
    """Test first run with failed zones."""
    ws66i = MockWs66i()

    with patch.object(MockWs66i, "zone_status", return_value=None):
        await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_1_ID)
    assert entry is None

    entry = registry.async_get(ZONE_7_ID)
    assert entry is None


async def test_register_all_entities(hass: HomeAssistant) -> None:
    """Test run with all entities registered."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_1_ID)
    assert not entry.disabled

    entry = registry.async_get(ZONE_7_ID)
    assert not entry.disabled


async def test_register_entities_in_1_amp_only(hass: HomeAssistant) -> None:
    """Test run with only zones 11-16 registered."""
    ws66i = MockWs66i(fail_zone_check=[21])
    await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_1_ID)
    assert not entry.disabled

    entry = registry.async_get(ZONE_2_ID)
    assert not entry.disabled

    entry = registry.async_get(ZONE_7_ID)
    assert entry is None
