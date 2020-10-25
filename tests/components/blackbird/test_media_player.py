"""The tests for the Monoprice Blackbird media player platform."""
from collections import defaultdict

import pytest
import voluptuous as vol

from homeassistant.components.blackbird.const import DOMAIN, SERVICE_SETALLZONES
from homeassistant.components.blackbird.media_player import (
    DATA_BLACKBIRD,
    PLATFORM_SCHEMA,
    async_setup_platform,
)
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
)
from homeassistant.const import STATE_OFF, STATE_ON

from tests.async_mock import patch


class AttrDict(dict):
    """Helper class for mocking attributes."""

    def __setattr__(self, name, value):
        """Set attribute."""
        self[name] = value

    def __getattr__(self, item):
        """Get attribute."""
        return self[item]


class MockBlackbird:
    """Mock for pyblackbird object."""

    def __init__(self):
        """Init mock object."""
        self.zones = defaultdict(lambda: AttrDict(power=True, av=1))

    def zone_status(self, zone_id):
        """Get zone status."""
        status = self.zones[zone_id]
        status.zone = zone_id
        return AttrDict(status)

    def set_zone_source(self, zone_id, source_idx):
        """Set source for zone."""
        self.zones[zone_id].av = source_idx

    def set_zone_power(self, zone_id, power):
        """Turn zone on/off."""
        self.zones[zone_id].power = power

    def set_all_zone_source(self, source_idx):
        """Set source for all zones."""
        self.zones[3].av = source_idx


class TestBlackbirdSchema:
    """Test Blackbird schema."""

    def test_valid_serial_schema(self):
        """Test valid schema."""
        valid_schema = {
            "platform": "blackbird",
            "port": "/dev/ttyUSB0",
            "zones": {
                1: {"name": "a"},
                2: {"name": "a"},
                3: {"name": "a"},
                4: {"name": "a"},
                5: {"name": "a"},
                6: {"name": "a"},
                7: {"name": "a"},
                8: {"name": "a"},
            },
            "sources": {
                1: {"name": "a"},
                2: {"name": "a"},
                3: {"name": "a"},
                4: {"name": "a"},
                5: {"name": "a"},
                6: {"name": "a"},
                7: {"name": "a"},
                8: {"name": "a"},
            },
        }
        PLATFORM_SCHEMA(valid_schema)

    def test_valid_socket_schema(self):
        """Test valid schema."""
        valid_schema = {
            "platform": "blackbird",
            "host": "192.168.1.50",
            "zones": {
                1: {"name": "a"},
                2: {"name": "a"},
                3: {"name": "a"},
                4: {"name": "a"},
                5: {"name": "a"},
            },
            "sources": {
                1: {"name": "a"},
                2: {"name": "a"},
                3: {"name": "a"},
                4: {"name": "a"},
            },
        }
        PLATFORM_SCHEMA(valid_schema)

    def test_invalid_schemas(self):
        """Test invalid schemas."""
        schemas = (
            {},  # Empty
            None,  # None
            # Port and host used concurrently
            {
                "platform": "blackbird",
                "port": "/dev/ttyUSB0",
                "host": "192.168.1.50",
                "name": "Name",
                "zones": {1: {"name": "a"}},
                "sources": {1: {"name": "b"}},
            },
            # Port or host missing
            {
                "platform": "blackbird",
                "name": "Name",
                "zones": {1: {"name": "a"}},
                "sources": {1: {"name": "b"}},
            },
            # Invalid zone number
            {
                "platform": "blackbird",
                "port": "/dev/ttyUSB0",
                "name": "Name",
                "zones": {11: {"name": "a"}},
                "sources": {1: {"name": "b"}},
            },
            # Invalid source number
            {
                "platform": "blackbird",
                "port": "/dev/ttyUSB0",
                "name": "Name",
                "zones": {1: {"name": "a"}},
                "sources": {9: {"name": "b"}},
            },
            # Zone missing name
            {
                "platform": "blackbird",
                "port": "/dev/ttyUSB0",
                "name": "Name",
                "zones": {1: {}},
                "sources": {1: {"name": "b"}},
            },
            # Source missing name
            {
                "platform": "blackbird",
                "port": "/dev/ttyUSB0",
                "name": "Name",
                "zones": {1: {"name": "a"}},
                "sources": {1: {}},
            },
        )
        for value in schemas:
            with pytest.raises(vol.MultipleInvalid):
                PLATFORM_SCHEMA(value)


@pytest.fixture
def blackbird():
    """Fixture to mock Blackbird."""
    yield MockBlackbird()


@pytest.fixture
async def media_player(hass, blackbird):
    """Fixture to provide test instance for media_player."""
    # Note, source dictionary is unsorted!
    with patch(
        "homeassistant.components.blackbird.media_player.get_blackbird",
        new=lambda *a: blackbird,
    ):
        await async_setup_platform(
            hass,
            {
                "platform": "blackbird",
                "port": "/dev/ttyUSB0",
                "zones": {3: {"name": "Zone name"}},
                "sources": {
                    1: {"name": "one"},
                    3: {"name": "three"},
                    2: {"name": "two"},
                },
            },
            lambda *args, **kwargs: None,
            {},
        )
        await hass.async_block_till_done()
    media_player = hass.data[DATA_BLACKBIRD]["/dev/ttyUSB0-3"]
    media_player.hass = hass
    media_player.entity_id = "media_player.zone_3"
    yield media_player


@pytest.fixture
async def setup_test_case(media_player):
    """Set up the test case."""
    pass


async def test_setup_platform(setup_test_case, hass):
    """Test setting up platform."""
    # One service must be registered
    assert hass.services.has_service(DOMAIN, SERVICE_SETALLZONES)
    assert len(hass.data[DATA_BLACKBIRD]) == 1
    assert hass.data[DATA_BLACKBIRD]["/dev/ttyUSB0-3"].name == "Zone name"


async def test_setallzones_service_call_with_entity_id(hass, blackbird, media_player):
    """Test set all zone source service call with entity id."""
    media_player.update()

    assert "Zone name" == media_player.name
    assert STATE_ON == media_player.state
    assert "one" == media_player.source

    # Call set all zones service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SETALLZONES,
        {"entity_id": "media_player.zone_3", "source": "three"},
        blocking=True,
    )

    # Check that source was changed
    assert 3 == blackbird.zones[3].av
    media_player.update()
    assert "three" == media_player.source


async def test_setallzones_service_call_without_entity_id(
    hass, blackbird, media_player
):
    """Test set all zone source service call without entity id."""
    media_player.update()
    assert "Zone name" == media_player.name
    assert STATE_ON == media_player.state
    assert "one" == media_player.source

    # Call set all zones service
    await hass.services.async_call(
        DOMAIN, SERVICE_SETALLZONES, {"source": "three"}, blocking=True
    )

    # Check that source was changed
    assert 3 == blackbird.zones[3].av
    media_player.update()
    assert "three" == media_player.source


async def test_update(media_player):
    """Test updating values from blackbird."""
    assert media_player.state is None
    assert media_player.source is None

    media_player.update()

    assert STATE_ON == media_player.state
    assert "one" == media_player.source


async def test_name(media_player):
    """Test name property."""
    assert "Zone name" == media_player.name


async def test_state(blackbird, media_player):
    """Test state property."""
    assert media_player.state is None

    media_player.update()
    assert STATE_ON == media_player.state

    blackbird.zones[3].power = False
    media_player.update()
    assert STATE_OFF == media_player.state


async def test_supported_features(media_player):
    """Test supported features property."""
    assert (
        SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE
        == media_player.supported_features
    )


async def test_source(media_player):
    """Test source property."""
    assert media_player.source is None
    media_player.update()
    assert "one" == media_player.source


async def test_media_title(media_player):
    """Test media title property."""
    assert media_player.media_title is None
    media_player.update()
    assert "one" == media_player.media_title


async def test_source_list(media_player):
    """Test source list property."""
    # Note, the list is sorted!
    assert ["one", "two", "three"] == media_player.source_list


async def test_select_source(blackbird, media_player):
    """Test source selection methods."""
    media_player.update()
    assert "one" == media_player.source

    media_player.select_source("two")
    assert 2 == blackbird.zones[3].av
    media_player.update()
    assert "two" == media_player.source

    # Trying to set unknown source.
    media_player.select_source("no name")
    assert 2 == blackbird.zones[3].av
    media_player.update()
    assert "two" == media_player.source


async def test_turn_on(blackbird, media_player):
    """Testing turning on the zone."""
    blackbird.zones[3].power = False
    media_player.update()
    assert STATE_OFF == media_player.state

    media_player.turn_on()
    assert blackbird.zones[3].power
    media_player.update()
    assert STATE_ON == media_player.state


async def test_turn_off(blackbird, media_player):
    """Testing turning off the zone."""
    blackbird.zones[3].power = True
    media_player.update()
    assert STATE_ON == media_player.state

    media_player.turn_off()
    assert not blackbird.zones[3].power
    media_player.update()
    assert STATE_OFF == media_player.state
