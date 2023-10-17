"""Config Flow Test for Olarm Sensors."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.olarm_sensors.config_flow import OlarmSensorsConfigFlow
from homeassistant.components.olarm_sensors.const import CONF_ALARM_CODE
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL


class TestOlarmSensorsConfigFlow(unittest.IsolatedAsyncioTestCase):
    """Config Flow Test for Olarm Sensors."""

    async def asyncSetUp(self):
        """Set up test instance."""
        self.hass = MagicMock()  # Create a mock Home Assistant instance
        self.flow = OlarmSensorsConfigFlow()
        self.flow.hass = self.hass
        self.flow.context = {"source": "user"}

    @patch("homeassistant.components.olarm_sensors.config_flow.OlarmSetupApi")
    async def test_config_flow_valid(self, mock_api):
        """Test the valid input."""
        mock_api_instance = AsyncMock()
        mock_api.return_value = mock_api_instance
        mock_api_instance.get_olarm_devices.return_value = [
            {
                "deviceName": "Device1",
                "deviceFirmware": "1.0",
                "deviceId": "123",
                "deviceAlarmType": "Type1",
            },
            {
                "deviceName": "Device2",
                "deviceFirmware": "1.1",
                "deviceId": "124",
                "deviceAlarmType": "Type2",
            },
        ]

        user_input = {
            CONF_API_KEY: "mock_api_key",
            CONF_SCAN_INTERVAL: 10,
            CONF_ALARM_CODE: "1234567890",
        }

        result = await self.flow.async_step_user(user_input)

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "Olarm Sensors")
        self.assertEqual(result["data"][CONF_API_KEY], "mock_api_key")
        self.assertEqual(result["data"][CONF_SCAN_INTERVAL], 10)
        self.assertEqual(result["data"][CONF_ALARM_CODE], None)

    async def test_config_flow_invalid(self):
        """Test the invalid input."""
        user_input = {
            CONF_API_KEY: "",
            CONF_SCAN_INTERVAL: 0,
            CONF_ALARM_CODE: "1234567890",
        }

        result = await self.flow.async_step_user(user_input)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"][CONF_API_KEY], "API key is required.")
        self.assertEqual(
            result["errors"][CONF_SCAN_INTERVAL], "Scan interval is required."
        )


if __name__ == "__main__":
    unittest.main()
