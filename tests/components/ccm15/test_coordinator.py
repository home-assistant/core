"""Unit test for CCM15 coordinator component."""
import unittest
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.ccm15 import CCM15Coordinator
from homeassistant.const import (
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_coordinator(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Coordinator._fetch_xml_data",
        return_value="<response><a0>000000b0b8001b,</a0><a1>00000041c0001a,</a1><a2>-</a2></response>",
    ):
        coordinator = CCM15Coordinator("1.1.1.1", "80", 30, hass)
        data = await coordinator._fetch_data()
        devices = coordinator.get_devices()

    assert len(data.devices) == 2
    first_climate = data.devices[0]
    assert first_climate is not None
    assert first_climate.temperature == 27
    assert first_climate.temperature_setpoint == 23
    assert first_climate.unit == UnitOfTemperature.CELSIUS

    assert len(devices) == 2


if __name__ == "__main__":
    unittest.main()
