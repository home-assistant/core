"""The tests for WS66i Media player platform."""
from collections import defaultdict
from unittest.mock import patch

import pytest

from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.components.ws66i.const import (
    CONF_SOURCES,
    DOMAIN,
    INIT_OPTIONS_DEFAULT,
    SERVICE_RESTORE,
    SERVICE_SNAPSHOT,
)
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

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


async def test_setup_success(hass):
    """Test connection success."""
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: MockWs66i(),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(ZONE_1_ID) is not None


async def _setup_ws66i(hass, ws66i) -> MockConfigEntry:
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: ws66i,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_DEFAULT_OPTIONS
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        return config_entry


async def _setup_ws66i_with_options(hass, ws66i) -> MockConfigEntry:
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: ws66i,
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        return config_entry


async def _call_media_player_service(hass, name, data):
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, name, service_data=data, blocking=True
    )


async def _call_ws66i_service(hass, name, data):
    await hass.services.async_call(DOMAIN, name, service_data=data, blocking=True)


async def test_cannot_connect(hass):
    """Test connection error."""
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: MockWs66i(fail_open=True),
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(ZONE_1_ID) is None


async def test_cannot_connect_2(hass):
    """Test connection error pt 2."""
    # Another way to test same case as test_cannot_connect
    ws66i = MockWs66i()

    with patch.object(MockWs66i, "open", side_effect=ConnectionError):
        await _setup_ws66i(hass, ws66i)
        assert hass.states.get(ZONE_1_ID) is None


async def test_service_calls_with_entity_id(hass):
    """Test snapshot save/restore service calls."""
    _ = await _setup_ws66i_with_options(hass, MockWs66i())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_ws66i_service(hass, SERVICE_SNAPSHOT, {"entity_id": ZONE_1_ID})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )
    await hass.async_block_till_done()

    # Restoring other media player to its previous state
    # The zone should not be restored
    with pytest.raises(HomeAssistantError):
        await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_2_ID})
        await hass.async_block_till_done()

    # Checking that values were not (!) restored
    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"

    # Restoring media player to its previous state
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_1_ID})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "one"


async def test_service_calls_with_all_entities(hass):
    """Test snapshot save/restore service calls with entity id all."""
    _ = await _setup_ws66i_with_options(hass, MockWs66i())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_ws66i_service(hass, SERVICE_SNAPSHOT, {"entity_id": "all"})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    # await coordinator.async_refresh()
    # await hass.async_block_till_done()

    # Restoring media player to its previous state
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": "all"})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "one"


async def test_service_calls_without_relevant_entities(hass):
    """Test snapshot save/restore service calls with bad entity id."""
    config_entry = await _setup_ws66i_with_options(hass, MockWs66i())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    ws66i_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ws66i_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Saving existing values
    await _call_ws66i_service(hass, SERVICE_SNAPSHOT, {"entity_id": "all"})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Restoring media player to its previous state
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": "light.demo"})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"


async def test_restore_without_snapshot(hass):
    """Test restore when snapshot wasn't called."""
    await _setup_ws66i(hass, MockWs66i())

    with patch.object(MockWs66i, "restore_zone") as method_call:
        with pytest.raises(HomeAssistantError):
            await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_1_ID})
            await hass.async_block_till_done()

        assert not method_call.called


async def test_update(hass):
    """Test updating values from ws66i."""
    ws66i = MockWs66i()
    config_entry = await _setup_ws66i_with_options(hass, ws66i)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    ws66i.set_source(11, 3)
    ws66i.set_volume(11, 38)

    ws66i_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ws66i_data.coordinator

    with patch.object(MockWs66i, "open") as method_call:
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert not method_call.called

    state = hass.states.get(ZONE_1_ID)

    assert hass.states.is_state(ZONE_1_ID, STATE_ON)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"


async def test_failed_update(hass):
    """Test updating failure from ws66i."""
    ws66i = MockWs66i()
    config_entry = await _setup_ws66i_with_options(hass, ws66i)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    ws66i.set_source(11, 3)
    ws66i.set_volume(11, 38)
    ws66i_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ws66i_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Failed update, close called
    with patch.object(MockWs66i, "zone_status", return_value=None):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_1_ID, STATE_UNAVAILABLE)

    # A connection re-attempt fails
    with patch.object(MockWs66i, "zone_status", return_value=None):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # A connection re-attempt succeeds
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # confirm entity is back on
    state = hass.states.get(ZONE_1_ID)

    assert hass.states.is_state(ZONE_1_ID, STATE_ON)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 1.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "three"


async def test_supported_features(hass):
    """Test supported features property."""
    await _setup_ws66i(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    assert (
        SUPPORT_VOLUME_MUTE
        | SUPPORT_VOLUME_SET
        | SUPPORT_VOLUME_STEP
        | SUPPORT_TURN_ON
        | SUPPORT_TURN_OFF
        | SUPPORT_SELECT_SOURCE
        == state.attributes["supported_features"]
    )


async def test_source_list(hass):
    """Test source list property."""
    await _setup_ws66i(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    # Note, the list is sorted!
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == list(
        INIT_OPTIONS_DEFAULT.values()
    )


async def test_source_list_with_options(hass):
    """Test source list property."""
    await _setup_ws66i_with_options(hass, MockWs66i())

    state = hass.states.get(ZONE_1_ID)
    # Note, the list is sorted!
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == list(MOCK_SOURCE_DIC.values())


async def test_select_source(hass):
    """Test source selection methods."""
    ws66i = MockWs66i()
    await _setup_ws66i_with_options(hass, ws66i)

    await _call_media_player_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {"entity_id": ZONE_1_ID, ATTR_INPUT_SOURCE: "three"},
    )
    assert ws66i.zones[11].source == 3


async def test_source_select(hass):
    """Test behavior when device has unknown source."""
    ws66i = MockWs66i()
    config_entry = await _setup_ws66i_with_options(hass, ws66i)

    ws66i.set_source(11, 5)

    ws66i_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ws66i_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes.get(ATTR_INPUT_SOURCE) == "five"


async def test_turn_on_off(hass):
    """Test turning on the zone."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    await _call_media_player_service(hass, SERVICE_TURN_OFF, {"entity_id": ZONE_1_ID})
    assert not ws66i.zones[11].power

    await _call_media_player_service(hass, SERVICE_TURN_ON, {"entity_id": ZONE_1_ID})
    assert ws66i.zones[11].power


async def test_mute_volume(hass):
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


async def test_volume_up_down(hass):
    """Test increasing volume by one."""
    ws66i = MockWs66i()
    config_entry = await _setup_ws66i(hass, ws66i)

    ws66i_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ws66i_data.coordinator

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    assert ws66i.zones[11].volume == 0

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    # should not go below zero
    assert ws66i.zones[11].volume == 0

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert ws66i.zones[11].volume == 1

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert ws66i.zones[11].volume == 38

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    # should not go above 38
    assert ws66i.zones[11].volume == 38

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    assert ws66i.zones[11].volume == 37


async def test_first_run_with_available_zones(hass):
    """Test first run with all zones available."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_7_ID)
    assert not entry.disabled


async def test_first_run_with_failing_zones(hass):
    """Test first run with failed zones."""
    ws66i = MockWs66i()

    with patch.object(MockWs66i, "zone_status", return_value=None):
        await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_1_ID)
    assert entry is None

    entry = registry.async_get(ZONE_7_ID)
    assert entry is None


async def test_register_all_entities(hass):
    """Test run with all entities registered."""
    ws66i = MockWs66i()
    await _setup_ws66i(hass, ws66i)

    registry = er.async_get(hass)

    entry = registry.async_get(ZONE_1_ID)
    assert not entry.disabled

    entry = registry.async_get(ZONE_7_ID)
    assert not entry.disabled


async def test_register_entities_in_1_amp_only(hass):
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


async def test_unload_config_entry(hass):
    """Test unloading config entry."""
    with patch(
        "homeassistant.components.ws66i.get_ws66i",
        new=lambda *a: MockWs66i(),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=MOCK_CONFIG, options=MOCK_OPTIONS
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.data[DOMAIN][config_entry.entry_id]

    with patch.object(MockWs66i, "close") as method_call:
        await config_entry.async_unload(hass)
        await hass.async_block_till_done()

        assert method_call.called

    assert not hass.data[DOMAIN]


async def test_restore_snapshot_on_reconnect(hass):
    """Test restoring a saved snapshot when reconnecting to amp."""
    ws66i = MockWs66i()
    config_entry = await _setup_ws66i_with_options(hass, ws66i)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Save a snapshot
    await _call_ws66i_service(hass, SERVICE_SNAPSHOT, {"entity_id": ZONE_1_ID})

    ws66i_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = ws66i_data.coordinator

    # Failed update,
    with patch.object(MockWs66i, "zone_status", return_value=None):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert hass.states.is_state(ZONE_1_ID, STATE_UNAVAILABLE)

    # A connection re-attempt succeeds
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # confirm entity is back on
    state = hass.states.get(ZONE_1_ID)

    assert hass.states.is_state(ZONE_1_ID, STATE_ON)
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "one"

    # Change states
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "six"}
    )

    # Now confirm that the snapshot before the disconnect works
    await _call_ws66i_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_1_ID})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.0
    assert state.attributes[ATTR_INPUT_SOURCE] == "one"
