"""The tests for the nextcloud sensor component."""

from unittest import TestCase

from homeassistant.components.nextcloud.sensor import NextcloudSensor

from tests.common import get_test_home_assistant, setup_component

API_RESPONSE = {"nextcloud_system_version": "17.0.3.1"}

VALID_CONFIG = {
    "sensor": {
        "platform": "nextcloud",
        "url": "https://nextcloud.sample.org",
        "username": "username",
        "password": "password",
    }
}

INVALID_CONFIG = {
    "sensor": {
        "platform": "nextcloud",
        "url": [],  # Url as empty list to invalidate configuration
        "username": "username",
        "password": "password",
    }
}


class testSensorSetup(TestCase):
    """Test the setup of the Nextcloud sensors."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.entities = []

    def tearDown(self):
        """Tear down after tests."""
        self.hass.stop()

    def test_valid_config(self):
        """Test setup using a valid configuration."""
        setup_component(self.hass, "sensor", VALID_CONFIG)

    def test_invalid_config(self):
        """Test setup using an invalid configuration."""
        setup_component(self.hass, "sensor", INVALID_CONFIG)


class test_NextcloudSensor(TestCase):
    """Tests the Nextcloud sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.ncs = NextcloudSensor("nextcloud_system_version")
        self.ncs.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.ncs.hass.stop()

    def test_init(self):
        """Tests initialization of NextcloudSensor class."""
        assert self.ncs._name == "nextcloud_system_version"
        assert self.ncs._state is None

    def test_icon(self):
        """Tests icon property."""
        assert self.ncs.icon == "mdi:cloud"

    def test_name(self):
        """Tests name property."""
        assert self.ncs.name == "nextcloud_system_version"

    def test_state(self):
        """Tests state property."""
        assert self.ncs.state is None

    def test_unique_id(self):
        """Tests unique_id property."""
        assert self.ncs.unique_id == "nextcloud_system_version"

    def test_update(self):
        """Tests update method."""
        self.ncs.hass.data["nextcloud"] = API_RESPONSE
        self.ncs.update()

        assert self.ncs._state == "17.0.3.1"
