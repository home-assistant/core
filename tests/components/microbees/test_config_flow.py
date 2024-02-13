"""Test the MicroBees config flow."""
import unittest
from unittest.mock import MagicMock, patch

from homeassistant.components.microbees import config_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

"""Test the MicroBees config flow."""


class TestMicroBeesConfigFlow(unittest.TestCase):
    """Test the MicroBees config flow."""

    def setUp(self):
        """Initialize test data."""
        self.hass = MagicMock(spec=HomeAssistant)
        self.entry = MagicMock(spec=ConfigEntry)

    @patch("microBeesPy.microbees.MicroBees")
    @patch("microBeesPy.microbees.MicroBees.getMyProfile")
    async def test_async_oauth_create_entry_success(
        self, mock_get_my_profile, mock_microbees
    ):
        """Test the entry success create."""
        mock_microbees_instance = MagicMock()
        mock_microbees.return_value = mock_microbees_instance
        mock_get_my_profile.return_value = MagicMock(username="test_user", id="12345")

        data = {"token": {"access_token": "mock-access-token"}}
        result = await config_flow.OAuth2FlowHandler(
            self.hass
        ).async_oauth_create_entry(data)
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "test_user")
        self.assertEqual(result["data"], data)

    @patch("microBeesPy.microbees.MicroBees")
    @patch("microBeesPy.microbees.MicroBees.getMyProfile")
    async def test_async_oauth_create_entry_invalid_auth(
        self, mock_get_my_profile, mock_microbees
    ):
        """Test the entry invalid auth."""
        mock_microbees_instance = MagicMock()
        mock_microbees.return_value = mock_microbees_instance
        mock_get_my_profile.side_effect = Exception("Invalid authentication")

        data = {"token": {"access_token": "mock-access-token"}}
        result = await config_flow.OAuth2FlowHandler(
            self.hass
        ).async_oauth_create_entry(data)
        """Test the MicroBees config flow."""
        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "invalid_auth")

    async def test_async_step_reauth(self):
        """Test the entry reauth."""
        handler = config_flow.OAuth2FlowHandler(self.hass)
        handler.context = {"entry_id": "123456"}

        with patch.object(
            handler.hass.config_entries, "async_get_entry", return_value=self.entry
        ) as mock_get_entry:
            """Test the MicroBees config flow."""
            result = await handler.async_step_reauth({})
            self.assertEqual(result["step_id"], "reauth_confirm")
            mock_get_entry.assert_called_once_with("123456")

    async def test_async_step_reauth_confirm(self):
        """Test the entry reauth confirm."""
        handler = config_flow.OAuth2FlowHandler(self.hass)
        handler.context = {"entry_id": "123456"}

        result = await handler.async_step_reauth_confirm({})
        self.assertEqual(result["type"], "form")

        result = await handler.async_step_reauth_confirm({"dummy_input": "dummy_value"})
        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "wrong_account")


if __name__ == "__main__":
    unittest.main()
