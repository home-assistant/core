"""Tests for Daikin Onecta platforms other than climate."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from daikin_onecta.client import OnectaClient
from daikin_onecta.models import Characteristic
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.daikin_onecta.binary_sensor import DaikinBinarySensor
from homeassistant.components.daikin_onecta.const import SENSOR_PERIOD_DAILY
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.components.daikin_onecta.entity_descriptions import (
    BINARY_SENSOR_DESCRIPTIONS,
    BUTTON_DESCRIPTIONS,
    SELECT_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    SWITCH_DESCRIPTIONS,
    UPDATE_DESCRIPTIONS,
)
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
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntityStateAttribute,
    FanServiceArgument,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE as WATER_HEATER_SERVICE_SET_TEMPERATURE,
    WaterHeaterServiceArgument,
    WaterHeaterStateAttribute,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .platform_helpers import _execute_typed_command
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


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
    entity._value = "test"
    entity._sub_type = None
    entity._period = SENSOR_PERIOD_DAILY
    entity._datatype = "consumed"
    entity._sensor_type = "electricity"
    entity._operation_mode = "heating"
    point = MagicMock()
    point.air_purification = SimpleNamespace(
        power=Characteristic(value="on", settable=True)
    )
    point.domestic_hot_water = object()
    point.energy_aggregates = [
        SimpleNamespace(
            data_type="consumed",
            source="electricity",
            operation_mode="heating",
            period="day",
        )
    ]
    point.firmware = SimpleNamespace(has_installed_version=True)
    point.schedule_state = SimpleNamespace(active_selection=object())
    characteristic = Characteristic(value="test")
    if entity_class is DaikinBinarySensor:
        characteristic = Characteristic(value=True)
    elif entity_class is DaikinSwitch:
        characteristic = Characteristic(value="on", settable=True, values=["on", "off"])
    point.scalar_characteristic.return_value = characteristic
    point.sensory_characteristic.return_value = characteristic
    entity._device = type(
        "Device",
        (),
        {
            "available": device_available,
            "management_point": lambda _, __: (
                point if management_point_exists else None
            ),
        },
    )
    entity._device = entity._device()

    assert entity.available is expected


def test_device_exposes_gateway_embedded_id() -> None:
    """Expose the gateway management point ID from the device wrapper."""
    gateway = _load_gateway_devices("altherma")[0]
    device = DaikinOnectaDevice(gateway)

    assert device.gateway_embedded_id == gateway.gateway_embedded_id


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
def test_removed_entity_capability_becomes_unavailable(entity_class: type) -> None:
    """Entities become unavailable when their source capability disappears."""
    entity = object.__new__(entity_class)
    entity.coordinator = SimpleNamespace(last_update_success=True)
    entity._embedded_id = "point"
    entity._value = "test"
    entity._sub_type = None
    entity._period = SENSOR_PERIOD_DAILY
    entity._datatype = "consumed"
    entity._sensor_type = "electricity"
    entity._operation_mode = "heating"
    point = MagicMock()
    point.air_purification = None
    point.domestic_hot_water = None
    point.energy_aggregates = []
    point.firmware = None
    point.schedule_state = None
    point.scalar_characteristic.return_value = None
    point.sensory_characteristic.return_value = None
    entity._device = SimpleNamespace(available=True, management_point=lambda _: point)

    assert not entity.available


async def test_account_entities_are_not_duplicated_for_multiple_gateways(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Create one account refresh and rate-limit entity for all gateways."""
    hass.config_entries.async_update_entry(config_entry, unique_id="account-id")

    await _async_setup_fixture(hass, config_entry, "climate_floorheatingairflow")

    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    refresh_entries = [entry for entry in entries if entry.domain == BUTTON_DOMAIN]
    rate_limit_entries = [
        entry
        for entry in entries
        if entry.domain == SENSOR_DOMAIN
        and entry.unique_id == "account-id_rate_limit_remaining_day"
    ]

    assert [entry.unique_id for entry in refresh_entries] == ["account-id_refresh"]
    assert len(rate_limit_entries) == 1


@pytest.mark.parametrize(
    "descriptions",
    [
        BINARY_SENSOR_DESCRIPTIONS,
        BUTTON_DESCRIPTIONS,
        SELECT_DESCRIPTIONS,
        SENSOR_DESCRIPTIONS,
        SWITCH_DESCRIPTIONS,
        UPDATE_DESCRIPTIONS,
    ],
)
def test_entity_descriptions_have_translation_keys(descriptions: dict) -> None:
    """Every described entity has a translated name."""
    assert all(
        description.translation_key is not None for description in descriptions.values()
    )


def test_primary_entities_use_device_name() -> None:
    """Primary device entities intentionally use the device name directly."""
    assert object.__new__(DaikinAirPurifier).name is None
    assert object.__new__(DaikinWaterTank).name is None


@pytest.mark.parametrize(
    ("fixture", "domain", "service", "entity_id", "data", "attribute", "expected"),
    [
        (
            "altherma_boost",
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            "water_heater.altherma_domestichotwatertank",
            {WaterHeaterServiceArgument.TEMPERATURE: 50},
            WaterHeaterStateAttribute.TARGET_TEMPERATURE,
            50,
        ),
        (
            "mc80z",
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            "fan.air_purifier_climatecontrol",
            {FanServiceArgument.PRESET_MODE: "auto_fan"},
            FanEntityStateAttribute.PRESET_MODE,
            "auto_fan",
        ),
        (
            "mc80z",
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            "fan.air_purifier_climatecontrol",
            {FanServiceArgument.PERCENTAGE: 100},
            FanEntityStateAttribute.PERCENTAGE,
            100,
        ),
    ],
)
async def test_command_cache_survives_model_replacement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fixture: str,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, str | int],
    attribute: str,
    expected: str | int,
) -> None:
    """Update the current model if polling replaces it while a command waits."""
    await _async_setup_fixture(hass, config_entry, fixture)
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
    coordinator.async_execute_command = execute

    async def replace_model(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        for device in coordinator.data.values():
            device.set_device_data(deepcopy(device.device))
        return await execute(command)

    coordinator.async_execute_command = AsyncMock(side_effect=replace_model)
    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[attribute] == expected
