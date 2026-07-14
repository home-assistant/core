"""Test for the Mammotion lawn_mower platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pymammotion.data.model.device import MowingDevice
from pymammotion.utility.constant.device_constant import WorkMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerActivity,
)
from homeassistant.components.mammotion.const import COMMAND_EXCEPTIONS, DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "lawn_mower.garden_luba"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mower_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("sys_status", "charge_state", "expected_state"),
    [
        pytest.param(WorkMode.MODE_WORKING, 0, LawnMowerActivity.MOWING, id="mowing"),
        pytest.param(WorkMode.MODE_PAUSE, 0, LawnMowerActivity.PAUSED, id="paused"),
        pytest.param(
            WorkMode.MODE_READY, 0, LawnMowerActivity.PAUSED, id="ready-undocked"
        ),
        pytest.param(WorkMode.MODE_READY, 1, LawnMowerActivity.DOCKED, id="docked"),
        pytest.param(
            WorkMode.MODE_RETURNING, 0, LawnMowerActivity.RETURNING, id="returning"
        ),
        pytest.param(WorkMode.MODE_LOCK, 0, LawnMowerActivity.ERROR, id="locked"),
        pytest.param(999, 0, STATE_UNKNOWN, id="unknown-mode"),
    ],
)
@pytest.mark.usefixtures("mock_mower_api")
async def test_activity(
    hass: HomeAssistant,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    sys_status: int,
    charge_state: int,
    expected_state: str,
) -> None:
    """Test the mower state reflects the reported device status."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    mock_mowing_device.report_data.dev.charge_state = charge_state

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "sys_status", "charge_state", "expected_commands"),
    [
        pytest.param(
            SERVICE_START_MOWING, WorkMode.MODE_READY, 0, ["start_job"], id="start"
        ),
        pytest.param(
            SERVICE_START_MOWING,
            WorkMode.MODE_PAUSE,
            0,
            ["resume_execute_task"],
            id="resume",
        ),
        pytest.param(
            SERVICE_DOCK,
            WorkMode.MODE_WORKING,
            0,
            ["pause_execute_task", "return_to_dock"],
            id="dock-while-mowing",
        ),
        pytest.param(
            SERVICE_DOCK, WorkMode.MODE_READY, 0, ["return_to_dock"], id="dock-ready"
        ),
        pytest.param(
            SERVICE_DOCK, WorkMode.MODE_RETURNING, 0, [], id="dock-already-returning"
        ),
        pytest.param(SERVICE_DOCK, WorkMode.MODE_READY, 1, [], id="dock-when-docked"),
        pytest.param(
            SERVICE_PAUSE, WorkMode.MODE_WORKING, 0, ["pause_execute_task"], id="pause"
        ),
        pytest.param(
            SERVICE_PAUSE,
            WorkMode.MODE_RETURNING,
            0,
            ["cancel_return_to_dock"],
            id="pause-returning",
        ),
        pytest.param(SERVICE_PAUSE, WorkMode.MODE_READY, 0, [], id="pause-idle"),
    ],
)
async def test_services(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    service: str,
    sys_status: int,
    charge_state: int,
    expected_commands: list[str],
) -> None:
    """Test the lawn mower services send the expected commands."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    mock_mowing_device.report_data.dev.charge_state = charge_state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LAWN_MOWER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert [
        call.args[1] for call in mock_mower_api.async_send_command.call_args_list
    ] == expected_commands
    assert mock_mower_api.async_request_iot_sync.call_count == (
        1 if expected_commands else 0
    )


@pytest.mark.parametrize(
    ("service", "sys_status", "expected_translation_key"),
    [
        pytest.param(
            SERVICE_START_MOWING, WorkMode.MODE_READY, "start_failed", id="start"
        ),
        pytest.param(
            SERVICE_START_MOWING, WorkMode.MODE_PAUSE, "resume_failed", id="resume"
        ),
        pytest.param(SERVICE_DOCK, WorkMode.MODE_WORKING, "pause_failed", id="dock"),
        pytest.param(SERVICE_PAUSE, WorkMode.MODE_WORKING, "pause_failed", id="pause"),
    ],
)
async def test_services_command_failure(
    hass: HomeAssistant,
    mock_mower_api: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    service: str,
    sys_status: int,
    expected_translation_key: str,
) -> None:
    """Test the lawn mower services raise on command failures."""
    mock_mowing_device.report_data.dev.sys_status = sys_status
    mock_mowing_device.report_data.dev.charge_state = 0
    mock_mower_api.async_send_command.side_effect = COMMAND_EXCEPTIONS[0]("boom")

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LAWN_MOWER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_translation_key
    assert mock_mower_api.async_request_iot_sync.call_count == 1


@pytest.mark.parametrize("service", [SERVICE_START_MOWING, SERVICE_DOCK, SERVICE_PAUSE])
@pytest.mark.usefixtures("mock_mower_api")
async def test_services_device_not_ready(
    hass: HomeAssistant,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test the lawn mower services raise when the device is not ready."""
    mock_mowing_device.report_data.dev.sys_status = None

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LAWN_MOWER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_not_ready"


async def test_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_mower_api: MagicMock,
    mock_mowing_device: MowingDevice,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entity becomes unavailable on failed updates or offline device."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    mock_mower_api.update.return_value = None
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_mower_api.update.return_value = mock_mowing_device
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    mock_mower_api.is_online.return_value = False
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
