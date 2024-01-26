"""Test Config flow for microBees integration."""
import unittest
from unittest.mock import patch

from homeassistant.components.microbees.config_flow import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class TestMicroBeesConfigFlow(unittest.TestCase):
    """Test the MicroBees config flow."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = self.create_patch("homeassistant.core.HomeAssistant")
        self.hass.config_entries = self.create_patch(
            "homeassistant.config_entries.ConfigEntries"
        )
        self.hass.helpers = self.create_patch("homeassistant.helpers")
        self.hass.helpers.aiohttp_client = async_get_clientsession
        self.flow = ConfigFlow()

    def create_patch(self, *args, **kwargs):
        """Create a patcher."""
        patcher = patch(*args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    async def test_async_step_user(self):
        """Test the async_step_user method."""
        result = await self.flow.async_step_user()
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")

    @patch("homeassistant.config_entries.SOURCE_REAUTH", "reauth")
    async def test_async_step_reauth(self):
        """Test the async_step_reauth method."""
        result = await self.flow.async_step_reauth({})
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "reauth_confirm")

    async def test_async_step_reauth_confirm(self):
        """Test the async_step_reauth_confirm method."""
        result = await self.flow.async_step_reauth_confirm({})
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "reauth_confirm")

        result = await self.flow.async_step_reauth_confirm({"key": "value"})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "John Doe")  # Adjust with your expected title

    @patch(
        "homeassistant.components.microbees.config_flow.MicroBeesConnector.getMyProfile"
    )
    async def test_async_oauth_create_entry(self, mock_get_my_profile):
        """Test the async_oauth_create_entry method."""
        mock_get_my_profile.return_value = MockMyProfile(
            id="123", firstName="John", lastName="Doe"
        )
        result = await self.flow.async_oauth_create_entry(
            {"token": {"access_token": "xyz"}}
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "John Doe")  # Adjust with your expected title
        self.assertEqual(result["data"]["id"], "123")


if __name__ == "__main__":
    unittest.main()
