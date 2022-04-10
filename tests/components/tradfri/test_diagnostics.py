"""Tests for Tradfri diagnostics."""
from unittest.mock import MagicMock, Mock

from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from .common import setup_integration
from .test_fan import mock_fan

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_gateway: Mock,
    mock_api_factory: MagicMock,
) -> None:
    """Test diagnostics for config entry."""
    mock_gateway.mock_devices.append(
        # Add a fan
        mock_fan(
            test_state={
                "fan_speed": 10,
                "air_quality": 42,
                "filter_lifetime_remaining": 120,
            }
        )
    )

    init_integration = await setup_integration(hass)

    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert isinstance(result, dict)
    assert result["gateway_version"] == "1.2.1234"
    assert len(result["device_data"]) == 1
