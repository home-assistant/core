"""The tests for the hddtemp platform."""
import socket
import unittest
from unittest.mock import patch

from homeassistant.const import TEMP_CELSIUS
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

VALID_CONFIG_MINIMAL = {"sensor": {"platform": "hddtemp"}}

VALID_CONFIG_NAME = {"sensor": {"platform": "hddtemp", "name": "FooBar"}}

VALID_CONFIG_ONE_DISK = {"sensor": {"platform": "hddtemp", "disks": ["/dev/sdd1"]}}

VALID_CONFIG_WRONG_DISK = {"sensor": {"platform": "hddtemp", "disks": ["/dev/sdx1"]}}

VALID_CONFIG_MULTIPLE_DISKS = {
    "sensor": {
        "platform": "hddtemp",
        "host": "foobar.local",
        "disks": ["/dev/sda1", "/dev/sdb1", "/dev/sdc1"],
    }
}

VALID_CONFIG_HOST = {"sensor": {"platform": "hddtemp", "host": "alice.local"}}

VALID_CONFIG_HOST_UNREACHABLE = {"sensor": {"platform": "hddtemp", "host": "bob.local"}}


class TelnetMock:
    """Mock class for the telnetlib.Telnet object."""

    def __init__(self, host, port, timeout=0):
        """Initialize Telnet object."""
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sample_data = bytes(
            "|/dev/sda1|WDC WD30EZRX-12DC0B0|29|C|"
            + "|/dev/sdb1|WDC WD15EADS-11P7B2|32|C|"
            + "|/dev/sdc1|WDC WD20EARX-22MMMB0|29|C|"
            + "|/dev/sdd1|WDC WD15EARS-00Z5B1|89|F|",
            "ascii",
        )

    def read_all(self):
        """Return sample values."""
        if self.host == "alice.local":
            raise ConnectionRefusedError
        if self.host == "bob.local":
            raise socket.gaierror
        return self.sample_data


class TestHDDTempSensor(unittest.TestCase):
    """Test the hddtemp sensor."""

    def setUp(self):
        """Set up things to run when tests begin."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG_ONE_DISK
        self.reference = {
            "/dev/sda1": {
                "device": "/dev/sda1",
                "temperature": "29",
                "unit_of_measurement": TEMP_CELSIUS,
                "model": "WDC WD30EZRX-12DC0B0",
            },
            "/dev/sdb1": {
                "device": "/dev/sdb1",
                "temperature": "32",
                "unit_of_measurement": TEMP_CELSIUS,
                "model": "WDC WD15EADS-11P7B2",
            },
            "/dev/sdc1": {
                "device": "/dev/sdc1",
                "temperature": "29",
                "unit_of_measurement": TEMP_CELSIUS,
                "model": "WDC WD20EARX-22MMMB0",
            },
            "/dev/sdd1": {
                "device": "/dev/sdd1",
                "temperature": "32",
                "unit_of_measurement": TEMP_CELSIUS,
                "model": "WDC WD15EARS-00Z5B1",
            },
        }
        self.addCleanup(self.hass.stop)

    @patch("telnetlib.Telnet", new=TelnetMock)
    def test_hddtemp_min_config(self):
        """Test minimal hddtemp configuration."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG_MINIMAL)
        self.hass.block_till_done()

        entity = self.hass.states.all()[0].entity_id
        state = self.hass.states.get(entity)

        reference = self.reference[state.attributes.get("device")]

        assert state.state == reference["temperature"]
        assert state.attributes.get("device") == reference["device"]
        assert state.attributes.get("model") == reference["model"]
        assert (
            state.attributes.get("unit_of_measurement")
            == reference["unit_of_measurement"]
        )
        assert (
            state.attributes.get("friendly_name")
            == f"HD Temperature {reference['device']}"
        )

    @patch("telnetlib.Telnet", new=TelnetMock)
    def test_hddtemp_rename_config(self):
        """Test hddtemp configuration with different name."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG_NAME)
        self.hass.block_till_done()

        entity = self.hass.states.all()[0].entity_id
        state = self.hass.states.get(entity)

        reference = self.reference[state.attributes.get("device")]

        assert state.attributes.get("friendly_name") == f"FooBar {reference['device']}"

    @patch("telnetlib.Telnet", new=TelnetMock)
    def test_hddtemp_one_disk(self):
        """Test hddtemp one disk configuration."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG_ONE_DISK)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.hd_temperature_dev_sdd1")

        reference = self.reference[state.attributes.get("device")]

        assert state.state == reference["temperature"]
        assert state.attributes.get("device") == reference["device"]
        assert state.attributes.get("model") == reference["model"]
        assert (
            state.attributes.get("unit_of_measurement")
            == reference["unit_of_measurement"]
        )
        assert (
            state.attributes.get("friendly_name")
            == f"HD Temperature {reference['device']}"
        )

    @patch("telnetlib.Telnet", new=TelnetMock)
    def test_hddtemp_wrong_disk(self):
        """Test hddtemp wrong disk configuration."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG_WRONG_DISK)
        self.hass.block_till_done()

        assert len(self.hass.states.all()) == 1
        state = self.hass.states.get("sensor.hd_temperature_dev_sdx1")
        assert state.attributes.get("friendly_name") == "HD Temperature /dev/sdx1"

    @patch("telnetlib.Telnet", new=TelnetMock)
    def test_hddtemp_multiple_disks(self):
        """Test hddtemp multiple disk configuration."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG_MULTIPLE_DISKS)
        self.hass.block_till_done()

        for sensor in [
            "sensor.hd_temperature_dev_sda1",
            "sensor.hd_temperature_dev_sdb1",
            "sensor.hd_temperature_dev_sdc1",
        ]:

            state = self.hass.states.get(sensor)

            reference = self.reference[state.attributes.get("device")]

            assert state.state == reference["temperature"]
            assert state.attributes.get("device") == reference["device"]
            assert state.attributes.get("model") == reference["model"]
            assert (
                state.attributes.get("unit_of_measurement")
                == reference["unit_of_measurement"]
            )
            assert (
                state.attributes.get("friendly_name")
                == f"HD Temperature {reference['device']}"
            )

    @patch("telnetlib.Telnet", new=TelnetMock)
    def test_hddtemp_host_refused(self):
        """Test hddtemp if host unreachable."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG_HOST)
        self.hass.block_till_done()
        assert len(self.hass.states.all()) == 0

    @patch("telnetlib.Telnet", new=TelnetMock)
    def test_hddtemp_host_unreachable(self):
        """Test hddtemp if host unreachable."""
        assert setup_component(self.hass, "sensor", VALID_CONFIG_HOST_UNREACHABLE)
        self.hass.block_till_done()
        assert len(self.hass.states.all()) == 0
