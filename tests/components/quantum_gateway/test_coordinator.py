"""Test the Quantum Gateway coordinator."""

from datetime import timedelta
from random import randint
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.quantum_gateway.coordinator import (
    QuantumGatewayCoordinator,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_platform

from tests.components.device_tracker.test_init import mock_yaml_devices  # noqa: F401


@pytest.mark.usefixtures("yaml_devices")
async def test_update_fails_when_unitialized(
    hass: HomeAssistant, mock_scanner: AsyncMock
) -> None:
    """Test the update interval is set from the options."""
    coordinator = QuantumGatewayCoordinator(hass, {})

    mock_scanner.assert_not_called()

    with pytest.raises(UpdateFailed, match="Scanner not initialized."):
        await coordinator._async_update_data()
