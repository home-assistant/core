"""Climate tests of Electrolux integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_appliance_id, merge_dict_recursive, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.electrolux.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.usefixtures("appliances")
async def test_climate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the climate."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    (
        "appliance_fixture",
        "entity_id",
        "appliance_state",
        "service",
        "data",
        "commands",
    ),
    [
        # set temperature command tests
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 20},
            [{"targetTemperatureC": 20}],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"temperatureRepresentation": "FAHRENHEIT", "targetTemperatureF": 70},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 26.6},
            [{"targetTemperatureF": 80.0}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {},
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 20},
            [{"airConditioner": {"targetTemperature": 20}}],
        ),
        # turn on/off command tests
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {},
            SERVICE_TURN_ON,
            {},
            [{"executeCommand": "ON"}],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {},
            SERVICE_TURN_OFF,
            {},
            [{"executeCommand": "OFF"}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {},
            SERVICE_TURN_ON,
            {},
            [{"airConditioner": {"executeCommand": "on"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {},
            SERVICE_TURN_OFF,
            {},
            [{"airConditioner": {"executeCommand": "off"}}],
        ),
        # set HVAC mode command tests
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING", "mode": "COOL"},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING"},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [{"mode": "COOL"}],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING"},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
            [{"mode": "FANONLY"}],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING"},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            [{"executeCommand": "OFF"}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running", "mode": "cool"}},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running", "mode": "dry"}},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [{"airConditioner": {"mode": "cool"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.AUTO},
            [{"airConditioner": {"mode": "auto"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.DRY},
            [{"airConditioner": {"mode": "dry"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.FAN_ONLY},
            [{"airConditioner": {"mode": "fanOnly"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.OFF},
            [{"airConditioner": {"executeCommand": "off"}}],
        ),
        # set HVAC mode while appliance off command tests
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "OFF"},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [{"executeCommand": "ON", "mode": "COOL"}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "off", "mode": None}},
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            [{"airConditioner": {"executeCommand": "on", "mode": "cool"}}],
        ),
        # set fan mode command tests
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING"},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_LOW},
            [{"fanSpeedSetting": "LOW"}],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING"},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_MEDIUM},
            [{"fanSpeedSetting": "MIDDLE"}],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING"},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_HIGH},
            [{"fanSpeedSetting": "HIGH"}],
        ),
        (
            "electrolux_ac",
            "climate.air_conditioner_climate",
            {"applianceState": "RUNNING"},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_AUTO},
            [{"fanSpeedSetting": "AUTO"}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_LOW},
            [{"airConditioner": {"fanMode": "low"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_MEDIUM},
            [{"airConditioner": {"fanMode": "medium"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_HIGH},
            [{"airConditioner": {"fanMode": "high"}}],
        ),
        (
            "electrolux_dam_ac",
            "climate.portable_air_conditioner_climate",
            {"airConditioner": {"applianceState": "running"}},
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_AUTO},
            [{"airConditioner": {"fanMode": "auto"}}],
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    appliances: AsyncMock,
    appliance_fixture: str,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    appliance_state: dict[str, Any],
    service: str,
    data: dict[str, Any],
    commands: list[dict[str, Any]],
) -> None:
    """Test climate set temperature command."""

    appliance_id = get_appliance_id(appliance_fixture)

    state = await appliances.get_appliance_state(appliance_id)
    state.properties["reported"] = merge_dict_recursive(
        state.properties["reported"], appliance_state
    )

    appliances.get_appliance_state.side_effect = None
    appliances.get_appliance_state.return_value = state

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id} | data,
        blocking=True,
    )
    assert appliances.send_command.mock_calls == [
        call(appliance_id, command) for command in commands
    ]
