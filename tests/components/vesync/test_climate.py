"""Tests for the climate platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pyvesync.const import ThermostatFanModes, ThermostatWorkModes
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .common import (
    ALL_DEVICE_NAMES,
    ENTITY_THERMOSTAT,
    THERMOSTAT_CLASS,
    mock_devices_response,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def us_customary_units(hass: HomeAssistant) -> None:
    """Use Fahrenheit so service temperatures reach the device unconverted."""
    hass.config.units = US_CUSTOMARY_SYSTEM


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_climate_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""
    mock_devices_response(aioclient_mock, device_name)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == CLIMATE_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("details_override", "expected_action"),
    [
        pytest.param({"workStatus": 1}, HVACAction.HEATING, id="heating"),
        pytest.param({"workStatus": 3}, HVACAction.HEATING, id="em_heating"),
        pytest.param({"workStatus": 2}, HVACAction.COOLING, id="cooling"),
        pytest.param({"workStatus": 0, "fanStatus": 1}, HVACAction.FAN, id="fan"),
        pytest.param({"workStatus": 0, "fanStatus": 0}, HVACAction.IDLE, id="idle"),
        pytest.param(
            {"workStatus": 0, "fanStatus": 0, "workMode": 0}, HVACAction.OFF, id="off"
        ),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    details_override: dict[str, Any],
    expected_action: HVACAction,
) -> None:
    """Test the HVAC action reported for each work status."""
    mock_devices_response(aioclient_mock, "Aura Thermostat", details_override)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_THERMOSTAT).attributes[ATTR_HVAC_ACTION] == (
        expected_action
    )


@pytest.mark.parametrize(
    ("work_mode", "expected"),
    [
        pytest.param(
            3,
            {ATTR_TARGET_TEMP_LOW: 68, ATTR_TARGET_TEMP_HIGH: 76},
            id="heat_cool",
        ),
        pytest.param(2, {ATTR_TEMPERATURE: 76}, id="cool"),
        pytest.param(4, {ATTR_TEMPERATURE: 68}, id="em_heat"),
    ],
)
async def test_target_temperatures(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    work_mode: int,
    expected: dict[str, float],
) -> None:
    """Test the target temperatures reported for each HVAC mode."""
    mock_devices_response(aioclient_mock, "Aura Thermostat", {"workMode": work_mode})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    attributes = hass.states.get(ENTITY_THERMOSTAT).attributes
    assert {key: attributes[key] for key in expected} == expected


@pytest.mark.parametrize(
    ("hvac_mode", "work_mode"),
    [
        (HVACMode.OFF, ThermostatWorkModes.OFF),
        (HVACMode.HEAT, ThermostatWorkModes.HEAT),
        (HVACMode.COOL, ThermostatWorkModes.COOL),
        (HVACMode.HEAT_COOL, ThermostatWorkModes.AUTO),
        (HVACMode.AUTO, ThermostatWorkModes.SMART_AUTO),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    thermostat_config_entry: MockConfigEntry,
    hvac_mode: HVACMode,
    work_mode: ThermostatWorkModes,
) -> None:
    """Test setting the HVAC mode."""
    with patch(
        f"{THERMOSTAT_CLASS}.set_mode", new=AsyncMock(return_value=True)
    ) as method_mock:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_THERMOSTAT, ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )

    method_mock.assert_awaited_once_with(work_mode)


@pytest.mark.usefixtures("thermostat_config_entry")
async def test_turn_off(hass: HomeAssistant) -> None:
    """Test turning the thermostat off."""
    with patch(
        f"{THERMOSTAT_CLASS}.set_mode", new=AsyncMock(return_value=True)
    ) as method_mock:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_THERMOSTAT},
            blocking=True,
        )

    method_mock.assert_awaited_once_with(ThermostatWorkModes.OFF)


@pytest.mark.parametrize(
    ("fan_mode", "vs_fan_mode"),
    [
        ("auto", ThermostatFanModes.AUTO),
        ("on", ThermostatFanModes.ON),
        ("circulate", ThermostatFanModes.CIRCULATE),
    ],
)
@pytest.mark.usefixtures("thermostat_config_entry")
async def test_set_fan_mode(
    hass: HomeAssistant,
    fan_mode: str,
    vs_fan_mode: ThermostatFanModes,
) -> None:
    """Test setting the fan mode."""
    with patch(
        f"{THERMOSTAT_CLASS}.set_fan_mode", new=AsyncMock(return_value=True)
    ) as method_mock:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_THERMOSTAT, ATTR_FAN_MODE: fan_mode},
            blocking=True,
        )

    method_mock.assert_awaited_once_with(vs_fan_mode)


@pytest.mark.usefixtures("thermostat_config_entry")
async def test_set_temperature(hass: HomeAssistant) -> None:
    """Test setting the target temperature in heat mode."""
    with (
        patch(
            f"{THERMOSTAT_CLASS}.set_heat_to_temp", new=AsyncMock(return_value=True)
        ) as heat_mock,
        patch(
            f"{THERMOSTAT_CLASS}.set_cool_to_temp", new=AsyncMock(return_value=True)
        ) as cool_mock,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_THERMOSTAT, ATTR_TEMPERATURE: 70},
            blocking=True,
        )

    heat_mock.assert_awaited_once_with(70)
    cool_mock.assert_not_awaited()


async def test_set_temperature_cool(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting the target temperature in cool mode."""
    mock_devices_response(aioclient_mock, "Aura Thermostat", {"workMode": 2})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            f"{THERMOSTAT_CLASS}.set_heat_to_temp", new=AsyncMock(return_value=True)
        ) as heat_mock,
        patch(
            f"{THERMOSTAT_CLASS}.set_cool_to_temp", new=AsyncMock(return_value=True)
        ) as cool_mock,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_THERMOSTAT, ATTR_TEMPERATURE: 74},
            blocking=True,
        )

    cool_mock.assert_awaited_once_with(74)
    heat_mock.assert_not_awaited()


async def test_set_temperature_range(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting the target temperature range in heat/cool mode."""
    mock_devices_response(aioclient_mock, "Aura Thermostat", {"workMode": 3})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            f"{THERMOSTAT_CLASS}.set_heat_to_temp", new=AsyncMock(return_value=True)
        ) as heat_mock,
        patch(
            f"{THERMOSTAT_CLASS}.set_cool_to_temp", new=AsyncMock(return_value=True)
        ) as cool_mock,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_THERMOSTAT,
                ATTR_TARGET_TEMP_LOW: 66,
                ATTR_TARGET_TEMP_HIGH: 78,
            },
            blocking=True,
        )

    heat_mock.assert_awaited_once_with(66)
    cool_mock.assert_awaited_once_with(78)


@pytest.mark.parametrize(
    ("method", "service", "service_data"),
    [
        pytest.param(
            "set_mode",
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            id="hvac_mode",
        ),
        pytest.param(
            "set_fan_mode",
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: "on"},
            id="fan_mode",
        ),
        pytest.param(
            "set_heat_to_temp",
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 70},
            id="temperature",
        ),
    ],
)
@pytest.mark.usefixtures("thermostat_config_entry")
async def test_service_failure(
    hass: HomeAssistant,
    method: str,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test a failed device call raises HomeAssistantError."""
    with (
        patch(f"{THERMOSTAT_CLASS}.{method}", new=AsyncMock(return_value=False)),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_THERMOSTAT, **service_data},
            blocking=True,
        )
