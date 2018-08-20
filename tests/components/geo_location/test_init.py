"""The tests for the geo location component."""
import unittest

from homeassistant.components import geo_location
from homeassistant.components.geo_location import GeoLocationEvent, \
    GeoLocationDeviceManager, DEFAULT_SORT_GROUP_ENTRIES_REVERSE, DOMAIN
from homeassistant.components.geo_location.demo import \
    DEFAULT_UNIT_OF_MEASUREMENT
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import callback
from homeassistant.setup import async_setup_component
from tests.common import get_test_home_assistant


async def test_setup_component(hass):
    """Simple test setup of component."""
    result = await async_setup_component(hass, geo_location.DOMAIN)
    assert result


class TestGeoLocationDeviceManager(unittest.TestCase):
    """Test the geo location event class."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def setup_manager(self):
        """Setup demo manager."""
        devices = []

        @callback
        def add_devices_callback(events):
            """Add recorded devices."""
            devices.extend(events)

        name = "manager name"
        sort_group_entries_reverse = DEFAULT_SORT_GROUP_ENTRIES_REVERSE
        return GeoLocationDeviceManager(self.hass, add_devices_callback, name,
                                        sort_group_entries_reverse)

    def test_manager(self):
        """Test geo location manager setup."""
        manager = self.setup_manager()
        assert manager._generate_entity_id("event name") \
            == "{}.manager_name_event_name".format(DOMAIN)


class TestGeoLocationEvent(unittest.TestCase):
    """Test the geo location event class."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_attributes(self):
        """Test attributes working as expected."""
        entity_id = "entity id 1"
        name = "name 1"
        distance = 10.123
        latitude = -33.0
        longitude = 151.0
        unit_of_measurement = DEFAULT_UNIT_OF_MEASUREMENT
        icon = "mdi:fire"
        event = GeoLocationEvent(self.hass, entity_id, name, distance,
                                 latitude, longitude, unit_of_measurement,
                                 icon)
        # Check all attributes.
        self.assertFalse(event.should_poll)
        assert event.name == name
        assert event.unit_of_measurement == DEFAULT_UNIT_OF_MEASUREMENT
        assert event.distance == distance
        assert event.state == 10.1
        assert event.latitude == latitude
        assert event.longitude == longitude
        assert event.icon == icon
        assert event.device_state_attributes == {
            ATTR_LATITUDE: latitude, ATTR_LONGITUDE: longitude}
        # Update some attributes and check again.
        event.name = "name 2"
        assert event.name == "name 2"
        event.distance = 20.234
        assert event.distance == 20.234
        event.latitude = -32.0
        assert event.latitude == -32.0
        event.longitude = 152.0
        assert event.longitude == 152.0
