"""Unit-tests for Swidget config_flow."""
import unittest
from unittest.mock import MagicMock, patch

from homeassistant.components.swidget import config_flow
from homeassistant.const import CONF_HOST, CONF_PASSWORD


class TestSwidgetConfigFlow(unittest.IsolatedAsyncioTestCase):
    """Class for the unit-tests for Swidget config_flow."""

    def setUp(self):
        """Set up each test case."""
        self.hass = MagicMock()
        self.config_flow = config_flow.ConfigFlow()

    async def test_async_step_user(self):
        """Test the async_step_user() config_flow function."""
        # Test successful validation
        with patch(
            "homeassistant.components.swidget.config_flow.validate_input",
            return_value={"title": "My Device"},
        ):
            result = await self.config_flow.async_step_user(
                {CONF_HOST: "example.com", CONF_PASSWORD: "password"}
            )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["title"], "My Device"
        )  # Ensure title is correctly returned

        # Test validation failure (cannot connect)
        with patch(
            "homeassistant.components.swidget.config_flow.validate_input",
            side_effect=config_flow.CannotConnect,
        ):
            result = await self.config_flow.async_step_user(
                {CONF_HOST: "example.com", CONF_PASSWORD: "password"}
            )
        self.assertEqual(result["type"], "form")
        self.assertIn("base", result["errors"])  # Ensure error is set

        # Test validation failure (invalid auth)
        with patch(
            "homeassistant.components.swidget.config_flow.validate_input",
            side_effect=config_flow.InvalidAuth,
        ):
            result = await self.config_flow.async_step_user(
                {CONF_HOST: "example.com", CONF_PASSWORD: "password"}
            )
        self.assertEqual(result["type"], "form")
        self.assertIn("base", result["errors"])  # Ensure error is set

        # Test unexpected exception during validation
        with patch(
            "homeassistant.components.swidget.config_flow.validate_input",
            side_effect=Exception,
        ):
            result = await self.config_flow.async_step_user(
                {CONF_HOST: "example.com", CONF_PASSWORD: "password"}
            )
        self.assertEqual(result["type"], "form")
        self.assertIn("base", result["errors"])  # Ensure error is set
