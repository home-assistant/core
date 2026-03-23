"""Test the services for the Switcher integration."""

from datetime import time
from unittest.mock import MagicMock, patch

from aioswitcher.api import Command
from aioswitcher.device import DeviceState
from aioswitcher.schedule import Days
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switcher_kis.const import (
    CONF_AUTO_OFF,
    CONF_SCHEDULE_DAYS,
    CONF_SCHEDULE_END_TIME,
    CONF_SCHEDULE_ID,
    CONF_SCHEDULE_START_TIME,
    CONF_TIMER_MINUTES,
    DOMAIN,
    SERVICE_CREATE_SCHEDULE_NAME,
    SERVICE_DELETE_SCHEDULE_NAME,
    SERVICE_GET_SCHEDULES_NAME,
    SERVICE_SET_AUTO_OFF_NAME,
    SERVICE_TURN_ON_WITH_TIMER_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceNotSupported,
    ServiceValidationError,
)
from homeassistant.helpers.config_validation import time_period_str
from homeassistant.util import slugify

from . import init_integration
from .consts import (
    DUMMY_AUTO_OFF_SET,
    DUMMY_HEATER_DEVICE,
    DUMMY_PLUG_DEVICE,
    DUMMY_TIMER_MINUTES_SET,
    DUMMY_TOKEN as TOKEN,
    DUMMY_USERNAME as USERNAME,
    DUMMY_WATER_HEATER_DEVICE,
)


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_turn_on_with_timer_service(
    hass: HomeAssistant, mock_bridge, mock_api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the turn on with timer service."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    # Test initial state - off
    monkeypatch.setattr(device, "device_state", DeviceState.OFF)
    mock_bridge.mock_callbacks([DUMMY_WATER_HEATER_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.control_device"
    ) as mock_control_device:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON_WITH_TIMER_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_TIMER_MINUTES: DUMMY_TIMER_MINUTES_SET,
            },
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(
            Command.ON, int(DUMMY_TIMER_MINUTES_SET)
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON


@pytest.mark.parametrize("mock_bridge", [[DUMMY_HEATER_DEVICE]], indirect=True)
async def test_turn_on_with_timer_service_token_needed(
    hass: HomeAssistant, mock_bridge, mock_api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the turn on with timer service."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    device = DUMMY_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    # Test initial state - off
    monkeypatch.setattr(device, "device_state", DeviceState.OFF)
    mock_bridge.mock_callbacks([DUMMY_HEATER_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.control_device"
    ) as mock_control_device:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON_WITH_TIMER_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_TIMER_MINUTES: DUMMY_TIMER_MINUTES_SET,
            },
            blocking=True,
        )

    assert mock_api.call_count == 2
    mock_control_device.assert_called_once_with(
        Command.ON, int(DUMMY_TIMER_MINUTES_SET)
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_set_auto_off_service(hass: HomeAssistant, mock_bridge, mock_api) -> None:
    """Test the set auto off service."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_auto_shutdown"
    ) as mock_set_auto_shutdown:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AUTO_OFF_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_set_auto_shutdown.assert_called_once_with(
            time_period_str(DUMMY_AUTO_OFF_SET)
        )


@pytest.mark.parametrize("mock_bridge", [[DUMMY_HEATER_DEVICE]], indirect=True)
async def test_set_auto_off_service_token_needed(
    hass: HomeAssistant, mock_bridge, mock_api
) -> None:
    """Test the set auto off service."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    device = DUMMY_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_auto_shutdown"
    ) as mock_set_auto_shutdown:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AUTO_OFF_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True,
        )

    assert mock_api.call_count == 2
    mock_set_auto_shutdown.assert_called_once_with(time_period_str(DUMMY_AUTO_OFF_SET))


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_set_auto_off_service_fail(
    hass: HomeAssistant, mock_bridge, mock_api
) -> None:
    """Test set auto off service failed."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_auto_shutdown",
        return_value=None,
    ) as mock_set_auto_shutdown:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_SET_AUTO_OFF_NAME,
                {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_set_auto_shutdown.assert_called_once_with(
            time_period_str(DUMMY_AUTO_OFF_SET)
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_bridge", [[DUMMY_HEATER_DEVICE]], indirect=True)
async def test_set_auto_off_service_fail_token_needed(
    hass: HomeAssistant, mock_bridge, mock_api
) -> None:
    """Test set auto off service failed."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    device = DUMMY_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with (
        patch(
            "homeassistant.components.switcher_kis.entity.SwitcherApi.set_auto_shutdown",
            return_value=None,
        ) as mock_set_auto_shutdown,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AUTO_OFF_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True,
        )

    assert mock_api.call_count == 2
    mock_set_auto_shutdown.assert_called_once_with(time_period_str(DUMMY_AUTO_OFF_SET))
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_bridge", [[DUMMY_PLUG_DEVICE]], indirect=True)
async def test_plug_unsupported_services(
    hass: HomeAssistant, mock_bridge, mock_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test plug device unsupported services."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_PLUG_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    # Turn on with timer
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON_WITH_TIMER_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_TIMER_MINUTES: DUMMY_TIMER_MINUTES_SET,
            },
            blocking=True,
        )

    assert mock_api.call_count == 0

    # Auto off
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AUTO_OFF_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True,
        )

    assert mock_api.call_count == 0

    # Get schedules
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SCHEDULES_NAME,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            return_response=True,
        )

    assert mock_api.call_count == 0

    # Create schedule
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SCHEDULE_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_SCHEDULE_START_TIME: time(7, 0),
                CONF_SCHEDULE_END_TIME: time(7, 30),
            },
            blocking=True,
        )

    assert mock_api.call_count == 0

    # Delete schedule
    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCHEDULE_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_SCHEDULE_ID: "0"},
            blocking=True,
        )

    assert mock_api.call_count == 0


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_get_schedules_service(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test the get schedules service."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    dummy_schedule = MagicMock()
    dummy_schedule.schedule_id = "0"
    dummy_schedule.recurring = True
    dummy_schedule.days = {Days.MONDAY, Days.FRIDAY}
    dummy_schedule.start_time = "07:00"
    dummy_schedule.end_time = "07:30"
    dummy_schedule.duration = "0:30:00"

    mock_response = MagicMock()
    mock_response.successful = True
    mock_response.schedules = {dummy_schedule}

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.get_schedules",
        return_value=mock_response,
    ) as mock_get_schedules:
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SCHEDULES_NAME,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            return_response=True,
        )

        assert mock_api.call_count == 2
        mock_get_schedules.assert_called_once_with()

    assert result is not None
    entity_result = result[entity_id]
    assert len(entity_result["schedules"]) == 1
    schedule = entity_result["schedules"][0]
    assert schedule["schedule_id"] == "0"
    assert schedule["recurring"] is True
    assert set(schedule["days"]) == {"monday", "friday"}
    assert schedule["start_time"] == "07:00"
    assert schedule["end_time"] == "07:30"
    assert schedule["duration"] == "0:30:00"


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_get_schedules_service_fail(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test the get schedules service when API call fails."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with (
        patch(
            "homeassistant.components.switcher_kis.entity.SwitcherApi.get_schedules",
            return_value=None,
        ) as mock_get_schedules,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SCHEDULES_NAME,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            return_response=True,
        )

    assert mock_api.call_count == 2
    mock_get_schedules.assert_called_once_with()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_create_schedule_service(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test the create schedule service (one-time schedule)."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.create_schedule"
    ) as mock_create_schedule:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SCHEDULE_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_SCHEDULE_START_TIME: time(7, 0),
                CONF_SCHEDULE_END_TIME: time(7, 30),
            },
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_create_schedule.assert_called_once_with("07:00", "07:30", set())


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_create_schedule_service_recurring(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test the create schedule service with recurring days."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.create_schedule"
    ) as mock_create_schedule:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SCHEDULE_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_SCHEDULE_START_TIME: time(7, 0),
                CONF_SCHEDULE_END_TIME: time(7, 30),
                CONF_SCHEDULE_DAYS: ["monday", "friday"],
            },
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_create_schedule.assert_called_once_with(
            "07:00", "07:30", {Days.MONDAY, Days.FRIDAY}
        )


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_create_schedule_service_end_before_start(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test create schedule raises ServiceValidationError when end_time <= start_time."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SCHEDULE_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_SCHEDULE_START_TIME: time(7, 30),
                CONF_SCHEDULE_END_TIME: time(7, 0),
            },
            blocking=True,
        )

    assert mock_api.call_count == 0


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_create_schedule_service_fail(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test create schedule service when API call fails."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with (
        patch(
            "homeassistant.components.switcher_kis.entity.SwitcherApi.create_schedule",
            return_value=None,
        ) as mock_create_schedule,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_SCHEDULE_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_SCHEDULE_START_TIME: time(7, 0),
                CONF_SCHEDULE_END_TIME: time(7, 30),
            },
            blocking=True,
        )

    assert mock_api.call_count == 2
    mock_create_schedule.assert_called_once_with("07:00", "07:30", set())
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_delete_schedule_service(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test the delete schedule service."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.delete_schedule"
    ) as mock_delete_schedule:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCHEDULE_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_SCHEDULE_ID: "0"},
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_delete_schedule.assert_called_once_with("0")


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_delete_schedule_service_fail(
    hass: HomeAssistant, mock_bridge: MagicMock, mock_api: MagicMock
) -> None:
    """Test delete schedule service when API call fails."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with (
        patch(
            "homeassistant.components.switcher_kis.entity.SwitcherApi.delete_schedule",
            return_value=None,
        ) as mock_delete_schedule,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCHEDULE_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_SCHEDULE_ID: "0"},
            blocking=True,
        )

    assert mock_api.call_count == 2
    mock_delete_schedule.assert_called_once_with("0")
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE
