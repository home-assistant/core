"""Tests for the Verisure sensor platform."""

from unittest.mock import MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import OVERVIEW

from tests.common import MockConfigEntry

ARM_STATUS_ENTITY_ID = "sensor.verisure_alarm_arm_status"

DRY_RUN_TRANSACTION = {"data": {"armStateDryRun": "dry-run-txn"}}
DRY_RUN_STATUS_VIOLATION = {
    "data": {
        "installation": {
            "armState": {
                "dryRunStatus": {
                    "status": {"status": "DONE"},
                    "result": {
                        "deviceViolations": [
                            {"deviceLabel": "door-1", "violation": "DOOR_WINDOW_OPEN"}
                        ]
                    },
                }
            }
        }
    }
}
DRY_RUN_STATUS_CLEAN = {
    "data": {
        "installation": {
            "armState": {
                "dryRunStatus": {
                    "status": {"status": "DONE"},
                    "result": {"deviceViolations": []},
                }
            }
        }
    }
}


async def _async_setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up the Verisure integration with the sensor platform."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.verisure.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_arm_status_bypass_needed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """The sensor reports bypass_needed when the dry run finds a violation."""
    mock_verisure.request.side_effect = [
        OVERVIEW,
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_VIOLATION,
    ]
    await _async_setup(hass, mock_config_entry)

    assert hass.states.get(ARM_STATUS_ENTITY_ID).state == "bypass_needed"


async def test_arm_status_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
) -> None:
    """The sensor reports ready when the dry run finds no violations."""
    mock_verisure.request.side_effect = [
        OVERVIEW,
        DRY_RUN_TRANSACTION,
        DRY_RUN_STATUS_CLEAN,
    ]
    await _async_setup(hass, mock_config_entry)

    assert hass.states.get(ARM_STATUS_ENTITY_ID).state == "ready"
