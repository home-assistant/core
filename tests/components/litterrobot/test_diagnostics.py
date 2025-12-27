"""Test Litter-Robot diagnostics."""

from unittest.mock import MagicMock

from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import setup_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, mock_account: MagicMock, hass_client: ClientSessionGenerator
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = await setup_integration(hass, mock_account, PLATFORM_DOMAIN)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == {
        "pets": [],
        "robots": [
            {
                "cleanCycleWaitTimeMinutes": "7",
                "cycleCapacity": "30",
                "cycleCount": "15",
                "cyclesAfterDrawerFull": "0",
                "lastSeen": "2022-09-17T13:06:37.884Z",
                "litterRobotId": "**REDACTED**",
                "litterRobotNickname": "Test",
                "litterRobotSerial": "**REDACTED**",
                "nightLightActive": "1",
                "panelLockActive": "0",
                "powerStatus": "AC",
                "sleepModeActive": "112:50:19",
                "unitStatus": "RDY",
            }
        ],
    }
