"""The tests for Monoprice Media player platform."""
from collections import defaultdict

from asynctest import patch
from serial import SerialException

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
from homeassistant.components.monoprice.const import (
    CONF_SOURCES,
    DOMAIN,
    SERVICE_RESTORE,
    SERVICE_SNAPSHOT,
)
from homeassistant.const import (
    CONF_PORT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import MockConfigEntry

MOCK_CONFIG = {CONF_PORT: "fake port", CONF_SOURCES: {"1": "one", "3": "three"}}

ZONE_1_ID = "media_player.zone_11"
ZONE_2_ID = "media_player.zone_12"


class AttrDict(dict):
    """Helper class for mocking attributes."""

    def __setattr__(self, name, value):
        """Set attribute."""
        self[name] = value

    def __getattr__(self, item):
        """Get attribute."""
        return self[item]


class MockMonoprice:
    """Mock for pymonoprice object."""

    def __init__(self):
        """Init mock object."""
        self.zones = defaultdict(
            lambda: AttrDict(power=True, volume=0, mute=True, source=1)
        )

    def zone_status(self, zone_id):
        """Get zone status."""
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


async def test_cannot_connect(hass):
    """Test connection error."""

    with patch(
        "homeassistant.components.monoprice.get_monoprice", side_effect=SerialException,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        # setup_component(self.hass, DOMAIN, MOCK_CONFIG)
        # self.hass.async_block_till_done()
        await hass.async_block_till_done()
        assert hass.states.get(ZONE_1_ID) is None


async def _setup_monoprice(hass, monoprice):
    with patch(
        "homeassistant.components.monoprice.get_monoprice", new=lambda *a: monoprice,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        # setup_component(self.hass, DOMAIN, MOCK_CONFIG)
        # self.hass.async_block_till_done()
        await hass.async_block_till_done()


async def _call_media_player_service(hass, name, data):
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, name, service_data=data, blocking=True
    )


async def _call_homeassistant_service(hass, name, data):
    await hass.services.async_call(
        "homeassistant", name, service_data=data, blocking=True
    )


async def _call_monoprice_service(hass, name, data):
    await hass.services.async_call(DOMAIN, name, service_data=data, blocking=True)


async def test_service_calls_with_entity_id(hass):
    """Test snapshot save/restore service calls."""
    await _setup_monoprice(hass, MockMonoprice())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_monoprice_service(hass, SERVICE_SNAPSHOT, {"entity_id": ZONE_1_ID})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    # Restoring other media player to its previous state
    # The zone should not be restored
    await _call_monoprice_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_2_ID})
    await hass.async_block_till_done()

    # Checking that values were not (!) restored
    state = hass.states.get(ZONE_1_ID)

    assert 1.0 == state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
    assert "three" == state.attributes[ATTR_INPUT_SOURCE]

    # Restoring media player to its previous state
    await _call_monoprice_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_1_ID})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert 0.0 == state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
    assert "one" == state.attributes[ATTR_INPUT_SOURCE]


async def test_service_calls_with_all_entities(hass):
    """Test snapshot save/restore service calls."""
    await _setup_monoprice(hass, MockMonoprice())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_monoprice_service(hass, SERVICE_SNAPSHOT, {"entity_id": "all"})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    # Restoring media player to its previous state
    await _call_monoprice_service(hass, SERVICE_RESTORE, {"entity_id": "all"})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert 0.0 == state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
    assert "one" == state.attributes[ATTR_INPUT_SOURCE]


async def test_service_calls_without_relevant_entities(hass):
    """Test snapshot save/restore service calls."""
    await _setup_monoprice(hass, MockMonoprice())

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    # Saving existing values
    await _call_monoprice_service(hass, SERVICE_SNAPSHOT, {"entity_id": "all"})

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "three"}
    )

    # Restoring media player to its previous state
    await _call_monoprice_service(hass, SERVICE_RESTORE, {"entity_id": "light.demo"})
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert 1.0 == state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
    assert "three" == state.attributes[ATTR_INPUT_SOURCE]


async def test_restore_without_snapshort(hass):
    """Test restore when snapshot wasn't called."""
    await _setup_monoprice(hass, MockMonoprice())

    with patch.object(MockMonoprice, "restore_zone") as method_call:
        await _call_monoprice_service(hass, SERVICE_RESTORE, {"entity_id": ZONE_1_ID})
        await hass.async_block_till_done()

        assert not method_call.called


async def test_update(hass):
    """Test updating values from monoprice."""
    """Test snapshot save/restore service calls."""
    monoprice = MockMonoprice()
    await _setup_monoprice(hass, monoprice)

    # Changing media player to new state
    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    await _call_media_player_service(
        hass, SERVICE_SELECT_SOURCE, {"entity_id": ZONE_1_ID, "source": "one"}
    )

    monoprice.set_source(11, 3)
    monoprice.set_volume(11, 38)

    await async_update_entity(hass, ZONE_1_ID)
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert 1.0 == state.attributes[ATTR_MEDIA_VOLUME_LEVEL]
    assert "three" == state.attributes[ATTR_INPUT_SOURCE]


async def test_supported_features(hass):
    """Test supported features property."""
    await _setup_monoprice(hass, MockMonoprice())

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
    await _setup_monoprice(hass, MockMonoprice())

    state = hass.states.get(ZONE_1_ID)
    # Note, the list is sorted!
    assert ["one", "three"] == state.attributes[ATTR_INPUT_SOURCE_LIST]


async def test_select_source(hass):
    """Test source selection methods."""
    monoprice = MockMonoprice()
    await _setup_monoprice(hass, monoprice)

    await _call_media_player_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {"entity_id": ZONE_1_ID, ATTR_INPUT_SOURCE: "three"},
    )
    assert 3 == monoprice.zones[11].source

    # Trying to set unknown source
    await _call_media_player_service(
        hass,
        SERVICE_SELECT_SOURCE,
        {"entity_id": ZONE_1_ID, ATTR_INPUT_SOURCE: "no name"},
    )
    assert 3 == monoprice.zones[11].source


async def test_unknown_source(hass):
    """Test behavior when device has unknown source."""
    monoprice = MockMonoprice()
    await _setup_monoprice(hass, monoprice)

    monoprice.set_source(11, 5)

    await async_update_entity(hass, ZONE_1_ID)
    await hass.async_block_till_done()

    state = hass.states.get(ZONE_1_ID)

    assert state.attributes.get(ATTR_INPUT_SOURCE) is None


async def test_turn_on_off(hass):
    """Test turning on the zone."""
    monoprice = MockMonoprice()
    await _setup_monoprice(hass, monoprice)

    await _call_media_player_service(hass, SERVICE_TURN_OFF, {"entity_id": ZONE_1_ID})
    assert not monoprice.zones[11].power

    await _call_media_player_service(hass, SERVICE_TURN_ON, {"entity_id": ZONE_1_ID})
    assert monoprice.zones[11].power


async def test_mute_volume(hass):
    """Test mute functionality."""
    monoprice = MockMonoprice()
    await _setup_monoprice(hass, monoprice)

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.5}
    )
    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": False}
    )
    assert not monoprice.zones[11].mute

    await _call_media_player_service(
        hass, SERVICE_VOLUME_MUTE, {"entity_id": ZONE_1_ID, "is_volume_muted": True}
    )
    assert monoprice.zones[11].mute


async def test_volume_up_down(hass):
    """Test increasing volume by one."""
    monoprice = MockMonoprice()
    await _setup_monoprice(hass, monoprice)

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 0.0}
    )
    assert 0 == monoprice.zones[11].volume

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    # should not go below zero
    assert 0 == monoprice.zones[11].volume

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})
    assert 1 == monoprice.zones[11].volume

    await _call_media_player_service(
        hass, SERVICE_VOLUME_SET, {"entity_id": ZONE_1_ID, "volume_level": 1.0}
    )
    assert 38 == monoprice.zones[11].volume

    await _call_media_player_service(hass, SERVICE_VOLUME_UP, {"entity_id": ZONE_1_ID})
    # should not go above 38
    assert 38 == monoprice.zones[11].volume

    await _call_media_player_service(
        hass, SERVICE_VOLUME_DOWN, {"entity_id": ZONE_1_ID}
    )
    assert 37 == monoprice.zones[11].volume
