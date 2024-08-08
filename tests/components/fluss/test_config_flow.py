from unittest.mock import MagicMock, patch  # noqa: D100

import pytest

from homeassistant.components.fluss import config_flow
from homeassistant.components.fluss.config_flow import CannotConnect, InvalidAuth
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Mock data for testing
MOCK_CONFIG = {config_flow.CONF_API_KEY: "mock_api_key"}


@pytest.fixture
def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    return MagicMock()


async def setup_fluss_config_flow(hass: HomeAssistant, config: dict) -> dict:  # noqa: D417
    """Set up the configuration flow for Fluss.

    Args:
    - hass (HomeAssistant): The Home Assistant instance.
    - config (dict): The configuration data for setting up Fluss.

    Returns:
    - dict: Result of the configuration flow.

    """
    with patch.object(
        config_flow, "validate_input", return_value={"title": "Mock Title"}
    ):
        return await config_flow.FlussConfigFlow().async_step_user(config)


@pytest.mark.asyncio
async def test_form_invalid_auth(mock_hass) -> None:
    """Test handling of invalid authentication."""
    with patch.object(config_flow, "validate_input", side_effect=InvalidAuth):
        result = await setup_fluss_config_flow(mock_hass, MOCK_CONFIG)
        assert result["type"] == FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_form_cannot_connect(mock_hass) -> None:
    """Test handling of connection errors."""
    with patch.object(config_flow, "validate_input", side_effect=CannotConnect):
        result = await setup_fluss_config_flow(mock_hass, MOCK_CONFIG)
        assert result["type"] == FlowResultType.CREATE_ENTRY
