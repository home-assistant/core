"""Test the APsystems Lake_6 immediate manual control."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.apsystems.lake6.client import (
    Lake6ControlPanel,
    parse_control_panel,
)
from homeassistant.components.apsystems.lake6.const import LAKE6_UPDATE_INTERVAL
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
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
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import LAKE6_ACTIVE_PAYLOAD, LAKE6_IDLE_PAYLOAD, setup_integration

MODE_ENTITY_ID = "select.mock_title_instant_manual_control"
POWER_ENTITY_ID = "number.mock_title_instant_manual_control_power"
DURATION_ENTITY_ID = "number.mock_title_instant_manual_control_duration"
APPLY_ENTITY_ID = "button.mock_title_send_instant_manual_control"
INTERRUPT_ENTITY_ID = "button.mock_title_stop_instant_manual_control"

# 10:00:00 UTC with a start 10 seconds in the past and a 30 minute window.
APPLIED_PAYLOAD = {
    "mode": "1",
    "MI1": {
        "time": ["2026112509595020261125103000"],
        "power": ["-500"],
    },
}


@pytest.fixture(autouse=True)
def mock_settle() -> Generator[AsyncMock]:
    """Skip the one second settle wait without freezing the loop clock."""
    with patch(
        "homeassistant.components.apsystems.coordinator.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        yield mock_sleep


async def test_apply_charge(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a charge request is staged, then sent with a negative power."""
    freezer.move_to("2026-11-25 10:00:00+00:00")
    await setup_integration(hass, mock_lake6_config_entry)
    mock_lake6.async_get_control_panel.return_value = parse_control_panel(
        LAKE6_ACTIVE_PAYLOAD
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "charge"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 500},
        target={TargetKey.ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 30},
        target={TargetKey.ENTITY_ID: DURATION_ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(APPLY_ENTITY_ID).state != "unavailable"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        target={TargetKey.ENTITY_ID: APPLY_ENTITY_ID},
        blocking=True,
    )

    mock_lake6.async_set_control_panel.assert_awaited_once_with(APPLIED_PAYLOAD)
    coordinator = mock_lake6_config_entry.runtime_data.coordinator
    assert coordinator.manual_control.last_sent_at is not None
    assert coordinator.manual_control.last_error is None


async def test_apply_standby_without_power(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test standby needs no wattage and always sends zero."""
    freezer.move_to("2026-11-25 10:00:00+00:00")
    await setup_integration(hass, mock_lake6_config_entry)
    mock_lake6.async_get_control_panel.return_value = parse_control_panel(
        LAKE6_ACTIVE_PAYLOAD
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "standby"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 10},
        target={TargetKey.ENTITY_ID: DURATION_ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(POWER_ENTITY_ID).state == "unavailable"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        target={TargetKey.ENTITY_ID: APPLY_ENTITY_ID},
        blocking=True,
    )

    mock_lake6.async_set_control_panel.assert_awaited_once_with(
        {
            "mode": "1",
            "MI1": {
                "time": ["2026112509595020261125101000"],
                "power": ["0"],
            },
        }
    )


async def test_apply_button_hidden_when_incomplete(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test a partial request hides the button instead of sending nothing."""
    await setup_integration(hass, mock_lake6_config_entry)

    assert hass.states.get(APPLY_ENTITY_ID).state == "unavailable"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "charge"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )

    # A mode without wattage and duration is still incomplete.
    assert hass.states.get(APPLY_ENTITY_ID).state == "unavailable"
    mock_lake6.async_set_control_panel.assert_not_awaited()


async def test_apply_rejects_incomplete_request(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test the coordinator refuses an incomplete request on its own."""
    await setup_integration(hass, mock_lake6_config_entry)

    coordinator = mock_lake6_config_entry.runtime_data.coordinator
    with pytest.raises(ServiceValidationError, match="mode, power, duration"):
        await coordinator.async_apply_manual_control()

    mock_lake6.async_set_control_panel.assert_not_awaited()


async def test_apply_not_applied(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test every timestamp layout and backdate is retried before giving up."""
    await setup_integration(hass, mock_lake6_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "discharge"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 300},
        target={TargetKey.ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 5},
        target={TargetKey.ENTITY_ID: DURATION_ENTITY_ID},
        blocking=True,
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            target={TargetKey.ENTITY_ID: APPLY_ENTITY_ID},
            blocking=True,
        )

    # Three backdates times two timestamp widths.
    assert mock_lake6.async_set_control_panel.await_count == 6
    coordinator = mock_lake6_config_entry.runtime_data.coordinator
    assert coordinator.manual_control.last_error == "device_not_running"
    # The staged request survives a rejection so it can be retried as typed.
    assert coordinator.manual_control.power == 300


async def test_interrupt(
    hass: HomeAssistant,
    mock_lake6_control_panel: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
) -> None:
    """Test stopping a running window clears the staged request."""
    await setup_integration(hass, mock_lake6_config_entry)
    mock_lake6_control_panel.async_get_control_panel.return_value = parse_control_panel(
        LAKE6_IDLE_PAYLOAD
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "discharge"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        target={TargetKey.ENTITY_ID: INTERRUPT_ENTITY_ID},
        blocking=True,
    )

    mock_lake6_control_panel.async_set_control_panel.assert_awaited_once_with(
        {"mode": "0", "MI1": {}}
    )
    coordinator = mock_lake6_config_entry.runtime_data.coordinator
    assert coordinator.manual_control.mode is None


async def test_finished_run_clears_staged_request(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a window that ends on its own also clears the staged request."""
    freezer.move_to("2026-11-25 10:00:00+00:00")
    await setup_integration(hass, mock_lake6_config_entry)
    mock_lake6.async_get_control_panel.return_value = parse_control_panel(
        LAKE6_ACTIVE_PAYLOAD
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "discharge"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 300},
        target={TargetKey.ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 5},
        target={TargetKey.ENTITY_ID: DURATION_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        target={TargetKey.ENTITY_ID: APPLY_ENTITY_ID},
        blocking=True,
    )

    coordinator = mock_lake6_config_entry.runtime_data.coordinator
    assert coordinator.manual_control.mode == "discharge"

    mock_lake6.async_get_control_panel.return_value = parse_control_panel(
        LAKE6_IDLE_PAYLOAD
    )
    freezer.tick(LAKE6_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.manual_control.mode is None
    assert coordinator.manual_control.power is None
    assert coordinator.manual_control.duration is None


async def test_apply_rounds_a_minute_precision_end_up(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the minute-precision layout does not cut the run short."""
    freezer.move_to("2026-11-25 10:00:59+00:00")
    await setup_integration(hass, mock_lake6_config_entry)
    mock_lake6.async_get_control_panel.return_value = parse_control_panel(
        LAKE6_IDLE_PAYLOAD
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "discharge"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 300},
        target={TargetKey.ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 1},
        target={TargetKey.ENTITY_ID: DURATION_ENTITY_ID},
        blocking=True,
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            target={TargetKey.ENTITY_ID: APPLY_ENTITY_ID},
            blocking=True,
        )

    payloads = [
        call.args[0] for call in mock_lake6.async_set_control_panel.await_args_list
    ]
    # Second precision: 10:00:49 to 10:01:59. The minute-precision layout drops
    # the seconds, so the end moves up to 10:02 instead of 10:01.
    assert payloads[0]["MI1"]["time"] == ["2026112510004920261125100159"]
    assert payloads[1]["MI1"]["time"] == ["202611251000202611251002"]


async def test_edit_during_send_survives_run_end(
    hass: HomeAssistant,
    mock_lake6: MagicMock,
    mock_lake6_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a value retyped while the send is in flight is not cleared."""
    freezer.move_to("2026-11-25 10:00:00+00:00")
    await setup_integration(hass, mock_lake6_config_entry)
    coordinator = mock_lake6_config_entry.runtime_data.coordinator

    async def _read_back_while_editing() -> Lake6ControlPanel:
        # The user retypes the wattage before the send completes.
        coordinator.manual_control.power = 999
        return parse_control_panel(LAKE6_ACTIVE_PAYLOAD)

    mock_lake6.async_get_control_panel.side_effect = _read_back_while_editing

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={ATTR_OPTION: "discharge"},
        target={TargetKey.ENTITY_ID: MODE_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 300},
        target={TargetKey.ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 5},
        target={TargetKey.ENTITY_ID: DURATION_ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        target={TargetKey.ENTITY_ID: APPLY_ENTITY_ID},
        blocking=True,
    )

    assert coordinator.manual_control.power == 999

    mock_lake6.async_get_control_panel.side_effect = None
    mock_lake6.async_get_control_panel.return_value = parse_control_panel(
        LAKE6_IDLE_PAYLOAD
    )
    freezer.tick(LAKE6_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The run ended on its own, but the request typed during the send was
    # never sent, so the cleanup must leave it alone.
    assert coordinator.manual_control.power == 999
