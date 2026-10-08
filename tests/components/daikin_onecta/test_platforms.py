"""Tests for Daikin Onecta platforms other than climate."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.daikin_onecta.binary_sensor import DaikinBinarySensor
from homeassistant.components.daikin_onecta.fan import DaikinAirPurifier
from homeassistant.components.daikin_onecta.select import DaikinScheduleSelect
from homeassistant.components.daikin_onecta.sensor import (
    DaikinEnergySensor,
    DaikinValueSensor,
)
from homeassistant.components.daikin_onecta.switch import DaikinSwitch
from homeassistant.components.daikin_onecta.update import DaikinFirmwareUpdateEntity
from homeassistant.components.daikin_onecta.water_heater import DaikinWaterTank
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN, SERVICE_SET_PRESET_MODE
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF as SWITCH_SERVICE_TURN_OFF,
)
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_TURN_OFF as WATER_HEATER_SERVICE_TURN_OFF,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_climate_snapshots import _async_setup_fixture

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "entity_class",
    [
        DaikinAirPurifier,
        DaikinBinarySensor,
        DaikinEnergySensor,
        DaikinFirmwareUpdateEntity,
        DaikinScheduleSelect,
        DaikinValueSensor,
        DaikinSwitch,
        DaikinWaterTank,
    ],
)
@pytest.mark.parametrize(
    ("last_update_success", "device_available", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_platform_availability_requires_coordinator_and_device(
    entity_class: type,
    last_update_success: bool,
    device_available: bool,
    expected: bool,
) -> None:
    """Entities are unavailable after failed polling or when their device is absent."""
    entity = object.__new__(entity_class)
    entity.coordinator = type(
        "Coordinator", (), {"last_update_success": last_update_success}
    )()
    entity._device = type("Device", (), {"available": device_available})()

    assert entity.available is expected


def _execute_typed_command(config_entry: MockConfigEntry) -> AsyncMock:
    """Execute a typed command callback without making a cloud request."""
    api = config_entry.runtime_data.api
    api.client.patch_characteristic = AsyncMock()
    api.client.put_management_point = AsyncMock()
    api.client.install_firmware = AsyncMock()

    async def execute(command) -> bool:
        await command(api.client)
        return True

    return AsyncMock(side_effect=execute)


async def test_refresh_button_requests_coordinator_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The refresh button requests one coordinator refresh."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    coordinator.async_refresh = AsyncMock()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.lounge_refresh"},
        blocking=True,
    )

    coordinator.async_refresh.assert_awaited_once()


async def test_management_point_device_links_to_gateway(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Management-point devices are linked to their registered gateway."""
    await _async_setup_fixture(hass, config_entry, "dry")

    climate_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == CLIMATE_DOMAIN
    )
    assert climate_entry.device_id is not None
    management_point = device_registry.async_get(climate_entry.device_id)

    assert management_point is not None
    assert management_point.via_device_id is not None
    gateway = device_registry.async_get(management_point.via_device_id)
    assert gateway is not None
    assert gateway.config_entry_id == config_entry.entry_id


async def test_switch_service_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful switch command updates the state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SWITCH_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.johnny_maaike_econo_mode"},
        blocking=True,
    )

    state = hass.states.get("switch.johnny_maaike_econo_mode")
    assert state is not None
    assert state.state == "off"


async def test_schedule_select_updates_cached_selection(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Selecting a schedule updates the entity state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.master_schedule", "option": "1"},
        blocking=True,
    )

    state = hass.states.get("select.master_schedule")
    assert state is not None
    assert state.state == "1"


async def test_water_heater_turn_off_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful water-heater command updates the cached operation mode."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "water_heater.altherma"},
        blocking=True,
    )

    state = hass.states.get("water_heater.altherma")
    assert state is not None
    assert state.attributes["operation_mode"] == "off"


async def test_firmware_install_executes_command(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The update service executes the typed firmware-install command."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.johnny_maaike_firmware_update"},
        blocking=True,
    )

    config_entry.runtime_data.api.async_execute_command.assert_awaited_once()
    state = hass.states.get("update.johnny_maaike_firmware_update")
    assert state is not None
    assert state.attributes["in_progress"] is False


async def test_air_purifier_preset_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful purifier command updates its native preset state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.air_purifier", "preset_mode": "autoFan"},
        blocking=True,
    )

    state = hass.states.get("fan.air_purifier")
    assert state is not None
    assert state.attributes["preset_mode"] == "autoFan"
