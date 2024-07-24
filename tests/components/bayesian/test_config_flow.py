"""Test the Config flow for the Bayesian integration."""

import pytest

from homeassistant.core import HomeAssistant


@pytest.mark.freeze_time("2024-07-09 00:00:00+00:00")
async def test_config_flow(hass: HomeAssistant) -> None:
    """Test the config flow."""
