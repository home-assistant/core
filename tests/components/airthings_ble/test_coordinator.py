"""Test the Airthings BLE coordinator."""

from airthings_ble import AirthingsDevice, AirthingsDeviceType
import pytest

from homeassistant.components.airthings_ble.const import DOMAIN
from homeassistant.components.airthings_ble.coordinator import (
    AirthingsBLEDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.components.bluetooth import MockConfigEntry


@pytest.mark.parametrize(
    ("connectivity_mode", "trigger_issue"),
    [
        ("SmartLink", True),
        ("Bluetooth", False),
        ("Unknown", False),
        (None, False),
    ],
)
async def test_connectivity_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    connectivity_mode: str,
    trigger_issue: bool,
) -> None:
    """Test that connectivity mode issue is created for SmartLink devices."""
    coordinator = AirthingsBLEDataUpdateCoordinator(
        hass=hass,
        entry=MockConfigEntry(
            domain=DOMAIN,
            unique_id="00:11:22:33:44:55",
        ),
    )
    data = AirthingsDevice(
        model=AirthingsDeviceType.CORENTIUM_HOME_2,
        address="00:11:22:33:44:55",
        sensors={"connectivity_mode": connectivity_mode},
    )
    await coordinator._check_connectivity_mode_issue(data=data)
    issue_id = f"smartlink_detected_{data.address}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    if trigger_issue:
        assert issue is not None
        assert issue.issue_id == issue_id
    else:
        assert issue is None
