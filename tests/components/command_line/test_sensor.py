"""The tests for the Command line sensor platform."""
import unittest

from homeassistant.components.command_line import sensor as command_line
from homeassistant.helpers.template import Template

from tests.async_mock import patch
from tests.common import get_test_home_assistant


class TestCommandSensorSensor(unittest.TestCase):
    """Test the Command line sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    def update_side_effect(self, data):
        """Side effect function for mocking CommandSensorData.update()."""
        self.commandline.data = data

    def test_setup(self):
        """Test sensor setup."""
        config = {
            "name": "Test",
            "unit_of_measurement": "in",
            "command": "echo 5",
            "command_timeout": 15,
        }
        devices = []

        def add_dev_callback(devs, update):
            """Add callback to add devices."""
            for dev in devs:
                devices.append(dev)

        command_line.setup_platform(self.hass, config, add_dev_callback)

        assert len(devices) == 1
        entity = devices[0]
        entity.update()
        assert entity.name == "Test"
        assert entity.unit_of_measurement == "in"
        assert entity.state == "5"

    def test_template(self):
        """Test command sensor with template."""
        data = command_line.CommandSensorData(self.hass, "echo 50", 15)

        entity = command_line.CommandSensor(
            self.hass,
            data,
            "test",
            "in",
            Template("{{ value | multiply(0.1) }}", self.hass),
            [],
        )

        entity.update()
        assert float(entity.state) == 5

    def test_template_render(self):
        """Ensure command with templates get rendered properly."""
        self.hass.states.set("sensor.test_state", "Works")
        data = command_line.CommandSensorData(
            self.hass, "echo {{ states.sensor.test_state.state }}", 15
        )
        data.update()

        assert data.value == "Works"

    def test_template_render_with_quote(self):
        """Ensure command with templates and quotes get rendered properly."""
        self.hass.states.set("sensor.test_state", "Works 2")
        with patch(
            "homeassistant.components.command_line.subprocess.check_output",
            return_value=b"Works\n",
        ) as check_output:
            data = command_line.CommandSensorData(
                self.hass, 'echo "{{ states.sensor.test_state.state }}" "3 4"', 15,
            )
            data.update()

        assert data.value == "Works"
        check_output.assert_called_once_with(
            'echo "Works 2" "3 4"', shell=True, timeout=15  # nosec # shell by design
        )

    def test_bad_command(self):
        """Test bad command."""
        data = command_line.CommandSensorData(self.hass, "asdfasdf", 15)
        data.update()

        assert data.value is None

    def test_update_with_json_attrs(self):
        """Test attributes get extracted from a JSON result."""
        data = command_line.CommandSensorData(
            self.hass,
            (
                'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
             \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }'
            ),
            15,
        )

        self.sensor = command_line.CommandSensor(
            self.hass, data, "test", None, None, ["key", "another_key", "key_three"]
        )
        self.sensor.update()
        assert self.sensor.device_state_attributes["key"] == "some_json_value"
        assert (
            self.sensor.device_state_attributes["another_key"] == "another_json_value"
        )
        assert self.sensor.device_state_attributes["key_three"] == "value_three"

    @patch("homeassistant.components.command_line.sensor._LOGGER")
    def test_update_with_json_attrs_no_data(self, mock_logger):
        """Test attributes when no JSON result fetched."""
        data = command_line.CommandSensorData(self.hass, "echo ", 15)
        self.sensor = command_line.CommandSensor(
            self.hass, data, "test", None, None, ["key"]
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called

    @patch("homeassistant.components.command_line.sensor._LOGGER")
    def test_update_with_json_attrs_not_dict(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        data = command_line.CommandSensorData(self.hass, "echo [1, 2, 3]", 15)
        self.sensor = command_line.CommandSensor(
            self.hass, data, "test", None, None, ["key"]
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called

    @patch("homeassistant.components.command_line.sensor._LOGGER")
    def test_update_with_json_attrs_bad_JSON(self, mock_logger):
        """Test attributes get extracted from a JSON result."""
        data = command_line.CommandSensorData(
            self.hass, "echo This is text rather than JSON data.", 15
        )
        self.sensor = command_line.CommandSensor(
            self.hass, data, "test", None, None, ["key"]
        )
        self.sensor.update()
        assert {} == self.sensor.device_state_attributes
        assert mock_logger.warning.called

    def test_update_with_missing_json_attrs(self):
        """Test attributes get extracted from a JSON result."""
        data = command_line.CommandSensorData(
            self.hass,
            (
                'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
             \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }'
            ),
            15,
        )

        self.sensor = command_line.CommandSensor(
            self.hass,
            data,
            "test",
            None,
            None,
            ["key", "another_key", "key_three", "special_key"],
        )
        self.sensor.update()
        assert self.sensor.device_state_attributes["key"] == "some_json_value"
        assert (
            self.sensor.device_state_attributes["another_key"] == "another_json_value"
        )
        assert self.sensor.device_state_attributes["key_three"] == "value_three"
        assert "special_key" not in self.sensor.device_state_attributes

    def test_update_with_unnecessary_json_attrs(self):
        """Test attributes get extracted from a JSON result."""
        data = command_line.CommandSensorData(
            self.hass,
            (
                'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\":\
             \\"another_json_value\\", \\"key_three\\": \\"value_three\\" }'
            ),
            15,
        )

        self.sensor = command_line.CommandSensor(
            self.hass, data, "test", None, None, ["key", "another_key"]
        )
        self.sensor.update()
        assert self.sensor.device_state_attributes["key"] == "some_json_value"
        assert (
            self.sensor.device_state_attributes["another_key"] == "another_json_value"
        )
        assert "key_three" not in self.sensor.device_state_attributes
