"""Tests for the Verisure alarm control panel."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    Platform,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ALARM_ENTITY_ID = "alarm_control_panel.verisure_alarm"
ARM_TRANSACTION = {"data": {"armStateChangeTransactionId": "txn"}}
POLL_OK = {"data": {"installation": {"armStateChangePollResult": {"result": "OK"}}}}


@pytest.mark.parametrize(
    ("service", "method", "state"),
    [
        (SERVICE_ALARM_ARM_AWAY, "arm_away", "armed_away"),
        (SERVICE_ALARM_ARM_HOME, "arm_home", "armed_home"),
    ],
)
async def test_arm_always_forces(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_verisure: MagicMock,
    service: str,
    method: str,
    state: str,
) -> None:
    """Arming always passes force_arm=True to the library."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.verisure.PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_verisure.request.side_effect = [ARM_TRANSACTION, POLL_OK]

    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ALARM_ENTITY_ID, "code": "1234"},
        blocking=True,
    )

    getattr(mock_verisure, method).assert_called_once_with("1234", force_arm=True)
    assert hass.states.get(ALARM_ENTITY_ID).state == state
