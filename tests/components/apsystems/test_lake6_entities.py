"""Test the APsystems Lake_6 writable entities."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.apsystems.lake6.client import Lake6ApiError
from homeassistant.components.apsystems.lake6.const import LAKE6_UPDATE_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SERVICE_TURN_ON
from homeassistant.components.text import (
    ATTR_VALUE as ATTR_TEXT_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE as SERVICE_SET_TEXT,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

DOD_ENTITY_ID = "number.mock_title_backup_soc"
ECO_ENTITY_ID = "switch.mock_title_economy_mode"
MODE_ENTITY_ID = "select.mock_title_device_operating_mode"
PLAN_ENTITY_ID = "text.mock_title_time_of_use_plan"
ISSUE_ID = "tou_power_dropped_LAKE6_SERIAL_NUMBER"
SCAN_INTERVAL = timedelta(seconds=LAKE6_UPDATE_INTERVAL)


@pytest.mark.usefixtures("mock_lake6")
async def test_number_writes_dod(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test a number write sends the string the device expects."""
    await setup_integration(hass, mock_lake6_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 20.7},
        target={TargetKey.ENTITY_ID: DOD_ENTITY_ID},
        blocking=True,
    )

    mock_lake6.async_set_modes.assert_awaited_once_with(dod="20")
    # Only /modes is re-read; energies and alarms keep their 60 second cadence.
    assert mock_lake6.async_get_modes.await_count == 2
    assert mock_lake6.async_get_energies.await_count == 1


@pytest.mark.usefixtures("mock_lake6")
async def test_switch_writes_flag(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test the switch maps its entity key back to the device field."""
    await setup_integration(hass, mock_lake6_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        target={TargetKey.ENTITY_ID: ECO_ENTITY_ID},
        blocking=True,
    )

    mock_lake6.async_set_modes.assert_awaited_once_with(eco="1")


@pytest.mark.usefixtures("mock_lake6")
async def test_select_writes_mode(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a mode writes the numeric code."""
    await setup_integration(hass, mock_lake6_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "self_consumption"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )

    mock_lake6.async_set_modes.assert_awaited_once_with(mode="2")


@pytest.mark.usefixtures("mock_lake6")
async def test_select_ai_is_rejected(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test AI mode cannot be entered from the integration."""
    await setup_integration(hass, mock_lake6_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            service_data={ATTR_OPTION: "ai"},
            target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
            blocking=True,
        )

    mock_lake6.async_set_modes.assert_not_awaited()


@pytest.mark.usefixtures("mock_lake6")
async def test_text_writes_plan(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test the schedule is written as a complete time_cfg array."""
    await setup_integration(hass, mock_lake6_config_entry)

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_TEXT,
        service_data={ATTR_TEXT_VALUE: "20:00-21:00|charge|500|67|1"},
        target={TargetKey.ENTITY_ID: PLAN_ENTITY_ID},
        blocking=True,
    )

    mock_lake6.async_set_modes.assert_awaited_once_with(
        time_cfg=[
            {
                "E": "1",
                "W": [6, 7],
                "TM": [
                    {
                        "T": "20002100",
                        "F": "1",
                        "FI": {"P": "500", "GC": 1},
                    }
                ],
            }
        ]
    )


@pytest.mark.usefixtures("mock_lake6")
async def test_text_rejects_invalid_plan(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test an unparsable schedule is refused before anything is written."""
    await setup_integration(hass, mock_lake6_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            TEXT_DOMAIN,
            SERVICE_SET_TEXT,
            service_data={ATTR_TEXT_VALUE: "20:00|charge|500|67|1"},
            target={TargetKey.ENTITY_ID: PLAN_ENTITY_ID},
            blocking=True,
        )

    mock_lake6.async_set_modes.assert_not_awaited()


@pytest.mark.usefixtures("mock_lake6")
async def test_text_reports_dropped_power(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a power on a self-consumption row raises a repair issue."""
    await setup_integration(hass, mock_lake6_config_entry)

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_TEXT,
        service_data={ATTR_TEXT_VALUE: "20:00-21:00|self|500|67|1"},
        target={TargetKey.ENTITY_ID: PLAN_ENTITY_ID},
        blocking=True,
    )

    issue = issue_registry.async_get_issue("apsystems", ISSUE_ID)
    assert issue is not None
    assert issue.translation_placeholders == {"rules": "1"}

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_TEXT,
        service_data={ATTR_TEXT_VALUE: "20:00-21:00|self|-|67|1"},
        target={TargetKey.ENTITY_ID: PLAN_ENTITY_ID},
        blocking=True,
    )

    assert issue_registry.async_get_issue("apsystems", ISSUE_ID) is None


async def test_failed_write_refreshes_modes(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a rejected write makes the next poll skip the five minute cache."""
    freezer.move_to("2026-11-25 10:00:00+00:00")
    await setup_integration(hass, mock_lake6_config_entry)
    assert mock_lake6.async_get_modes.await_count == 1

    mock_lake6.async_set_modes.side_effect = Lake6ApiError("rejected")
    with pytest.raises(Lake6ApiError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            target={TargetKey.ENTITY_ID: ECO_ENTITY_ID},
            blocking=True,
        )
    mock_lake6.async_set_modes.side_effect = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_lake6.async_get_modes.await_count == 2


async def test_write_keeps_the_poll_schedule(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write does not postpone the energies and alarms polling."""
    freezer.move_to("2026-11-25 10:00:00+00:00")
    await setup_integration(hass, mock_lake6_config_entry)
    assert mock_lake6.async_get_energies.await_count == 1

    freezer.tick(SCAN_INTERVAL / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        target={TargetKey.ENTITY_ID: ECO_ENTITY_ID},
        blocking=True,
    )

    freezer.tick(SCAN_INTERVAL / 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_lake6.async_get_energies.await_count == 2
