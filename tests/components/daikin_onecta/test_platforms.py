"""Tests for Daikin Onecta platforms other than climate."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
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
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PRESET_MODE,
    FanEntityFeature,
)
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
    SERVICE_SET_TEMPERATURE as WATER_HEATER_SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF as WATER_HEATER_SERVICE_TURN_OFF,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

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
    ("last_update_success", "device_available", "management_point_exists", "expected"),
    [
        (True, True, True, True),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
def test_platform_availability_requires_coordinator_and_device(
    entity_class: type,
    last_update_success: bool,
    device_available: bool,
    management_point_exists: bool,
    expected: bool,
) -> None:
    """Entities require a successful update and their management point."""
    entity = object.__new__(entity_class)
    entity.coordinator = type(
        "Coordinator", (), {"last_update_success": last_update_success}
    )()
    entity._embedded_id = "point"
    entity._device = type(
        "Device",
        (),
        {
            "available": device_available,
            "management_point": lambda _, __: (
                object() if management_point_exists else None
            ),
        },
    )()

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


async def test_water_heater_temperature_updates_typed_cache(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful temperature write updates the shared typed model."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "water_heater.altherma", ATTR_TEMPERATURE: 50},
        blocking=True,
    )

    management_point = next(
        point
        for device in config_entry.runtime_data.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    assert management_point.domestic_hot_water is not None
    assert management_point.domestic_hot_water.temperature is not None
    assert management_point.domestic_hot_water.temperature.value == 50


async def test_water_heater_publishes_successful_partial_operation_write() -> None:
    """Keep the successful power write visible if powerful mode later fails."""
    entity = object.__new__(DaikinWaterTank)
    power = SimpleNamespace(value="off", settable=True)
    powerful_mode = SimpleNamespace(value="off", settable=True)
    hot_water = SimpleNamespace(
        power=power,
        powerful_mode=powerful_mode,
        temperature=None,
        current_temperature=None,
    )
    entity._device = MagicMock(
        name="Tank",
        management_point=MagicMock(
            return_value=SimpleNamespace(
                domestic_hot_water=hot_water,
                on_off_mode=power,
            )
        ),
    )
    entity._embedded_id = "tank"
    entity._attr_current_operation = "off"
    entity._attr_operation_list = ["off", STATE_HEAT_PUMP, STATE_PERFORMANCE]
    entity._async_execute_hot_water_command = AsyncMock(
        side_effect=[None, HomeAssistantError]
    )
    entity.async_write_ha_state = MagicMock()

    with pytest.raises(HomeAssistantError):
        await entity.async_set_operation_mode(STATE_PERFORMANCE)

    assert power.value == "on"
    assert entity.current_operation == STATE_HEAT_PUMP
    entity.async_write_ha_state.assert_called_once()


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


async def test_air_purifier_does_not_expose_read_only_preset_modes() -> None:
    """Do not expose a preset service for a read-only Daikin mode."""
    entity = object.__new__(DaikinAirPurifier)
    purification = SimpleNamespace(
        power=SimpleNamespace(value="on"),
        mode=SimpleNamespace(value="autoFan", settable=False),
        modes=["autoFan", "manualFan"],
        fan_operation=MagicMock(return_value=None),
    )
    entity._air_purification = MagicMock(return_value=purification)
    entity._device = SimpleNamespace(name="Purifier")

    entity._update_state()

    assert entity.supported_features == (
        FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    assert entity.preset_modes == []
    with pytest.raises(HomeAssistantError):
        await entity.async_set_preset_mode("manualFan")


def test_unknown_binary_sensor_uses_generic_description() -> None:
    """A new boolean cloud characteristic must not prevent platform setup."""
    device = MagicMock(id="device", name="Device")
    device.management_point.return_value = SimpleNamespace(
        scalar_characteristic=MagicMock(return_value=SimpleNamespace(value=True))
    )

    entity = DaikinBinarySensor(
        device, MagicMock(), "point", "climateControl", "futureBoolean"
    )

    assert entity.entity_description.key == "futureBoolean"
    assert entity.is_on is True
