"""Tests for Imou datetime platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.const import PARAM_STATE, PARAM_STATUS
from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import DeviceStatus, ImouHaDevice
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.datetime import (
    ATTR_DATETIME,
    DOMAIN as DATETIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.imou.const import (
    PARAM_COUNT_DOWN_SWITCH,
    PARAM_PLUG_SWITCH,
)
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DEFAULT_PLUG_TEXTS, create_online_device

DEFAULT_PLUG_SWITCHES = {
    PARAM_PLUG_SWITCH: {PARAM_STATE: True},
}


def plug_mock_devices() -> list[ImouHaDevice]:
    """Return a fresh smart-plug device list for each test."""
    return [
        create_online_device(
            "plug1",
            "Smart plug",
            button_keys=(),
            switches=DEFAULT_PLUG_SWITCHES,
            texts=DEFAULT_PLUG_TEXTS,
        )
    ]


@pytest.mark.parametrize("platforms", [[Platform.DATETIME]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_datetime_entities_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot datetime entities created from the mock plug."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("platforms", [[Platform.DATETIME]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_set_countdown_end(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    imou_mock_devices: list[ImouHaDevice],
) -> None:
    """Setting an end time writes remaining minutes and keeps a stable timestamp."""
    entity_id = "datetime.smart_plug_turn_off_at"
    device = imou_mock_devices[0]
    now = dt_util.utcnow()
    freezer.move_to(now)
    end = now + timedelta(minutes=15)

    async def _set_countdown(dev: ImouHaDevice, text_type: str, value: str) -> None:
        device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] = value

    mock_imou_ha_device_manager.async_set_text_value.side_effect = _set_countdown

    await hass.services.async_call(
        DATETIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_DATETIME: end},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_imou_ha_device_manager.async_set_text_value.assert_called_once_with(
        device,
        PARAM_COUNT_DOWN_SWITCH,
        "15",
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == end.isoformat(timespec="seconds")
    # End time stays fixed; there is no per-minute listener rewriting state.
    freezer.tick(timedelta(minutes=1))
    assert hass.states.get(entity_id).state == end.isoformat(timespec="seconds")
    assert mock_config_entry.runtime_data.countdown.ends_at(device.device_id) == end


@pytest.mark.parametrize("platforms", [[Platform.DATETIME]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_set_countdown_imou_exception(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imou_ha_device_manager: MagicMock,
) -> None:
    """Cloud errors from set_text_value surface as translated failures."""
    mock_imou_ha_device_manager.async_set_text_value.side_effect = ImouException(
        "rejected"
    )
    end = dt_util.utcnow() + timedelta(minutes=10)
    freezer.move_to(dt_util.utcnow())

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DATETIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "datetime.smart_plug_turn_off_at",
                ATTR_DATETIME: end,
            },
            blocking=True,
        )


@pytest.mark.parametrize("platforms", [[Platform.DATETIME]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_countdown_expires_to_unknown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_imou_ha_device_manager: MagicMock,
    imou_mock_devices: list[ImouHaDevice],
) -> None:
    """When the end is reached, the datetime clears without minute ticks."""
    entity_id = "datetime.smart_plug_turn_off_at"
    device = imou_mock_devices[0]
    now = dt_util.utcnow()
    freezer.move_to(now)
    end = now + timedelta(minutes=1)

    async def _set_countdown(dev: ImouHaDevice, text_type: str, value: str) -> None:
        device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] = value

    mock_imou_ha_device_manager.async_set_text_value.side_effect = _set_countdown

    await hass.services.async_call(
        DATETIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_DATETIME: end},
        blocking=True,
    )
    await hass.async_block_till_done()

    freezer.move_to(end + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] == "0"


@pytest.mark.parametrize("platforms", [[Platform.DATETIME]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_countdown_cancelled_when_device_leaves_account(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    imou_mock_devices: list[ImouHaDevice],
) -> None:
    """Removing the last device cancels its local end before sync_all."""
    entity_id = "datetime.smart_plug_turn_off_at"
    device = imou_mock_devices[0]
    device_key = device.device_id
    coordinator = mock_config_entry.runtime_data
    now = dt_util.utcnow()
    freezer.move_to(now)

    async def _set_countdown(dev: ImouHaDevice, text_type: str, value: str) -> None:
        device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] = value

    mock_imou_ha_device_manager.async_set_text_value.side_effect = _set_countdown

    await hass.services.async_call(
        DATETIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_DATETIME: now + timedelta(minutes=10)},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coordinator.countdown.ends_at(device_key) is not None

    mock_imou_ha_device_manager.async_get_devices.return_value = []
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.countdown.ends_at(device_key) is None


@pytest.mark.parametrize("platforms", [[Platform.DATETIME]], indirect=True)
@pytest.mark.parametrize("imou_mock_devices", [plug_mock_devices], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_countdown_preserves_deadline_while_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    imou_mock_devices: list[ImouHaDevice],
) -> None:
    """Offline status polls must not reset the local end from stale text."""
    entity_id = "datetime.smart_plug_turn_off_at"
    device = imou_mock_devices[0]
    device_key = device.device_id
    coordinator = mock_config_entry.runtime_data
    now = dt_util.utcnow()
    freezer.move_to(now)
    end = now + timedelta(minutes=10)

    async def _set_countdown(dev: ImouHaDevice, text_type: str, value: str) -> None:
        device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] = value

    mock_imou_ha_device_manager.async_set_text_value.side_effect = _set_countdown

    await hass.services.async_call(
        DATETIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_DATETIME: end},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coordinator.countdown.ends_at(device_key) == end

    async def _mark_offline(devices: list[ImouHaDevice]) -> set[str]:
        device.sensors[PARAM_STATUS][PARAM_STATE] = DeviceStatus.OFFLINE.value
        return set()

    mock_imou_ha_device_manager.async_update_devices_status.side_effect = _mark_offline
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device.texts[PARAM_COUNT_DOWN_SWITCH][PARAM_STATE] == "10"
    assert coordinator.countdown.ends_at(device_key) == end
    # Offline devices are unavailable, but the local end time is unchanged.
    assert hass.states.get(entity_id).state == "unavailable"
