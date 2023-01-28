"""Tests for Tradfri diagnostics."""
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

from homeassistant.core import HomeAssistant

from .common import setup_integration
from .test_sensor import mock_fan

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
def setup(request):
    """Set up patches for pytradfri methods for the fan platform.

    This is used in test_fan as well as in test_sensor.
    """
    with patch(
        "pytradfri.device.AirPurifierControl.raw",
        new_callable=PropertyMock,
        return_value=[{"mock": "mock"}],
    ), patch(
        "pytradfri.device.AirPurifierControl.air_purifiers",
    ):
        yield


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
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
    assert result["device_data"] == ["model"]
