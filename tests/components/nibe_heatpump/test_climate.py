"""Test the Nibe Heat Pump config flow."""

from typing import Any
from unittest.mock import call, patch

from nibe.coil import CoilData
from nibe.coil_groups import (
    CLIMATE_COILGROUPS,
    UNIT_COILGROUPS,
    ClimateCoilGroup,
    UnitCoilGroup,
)
from nibe.heatpump import Model
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import MockConnection, async_add_model


@pytest.fixture(autouse=True)
async def fixture_single_platform():
    """Only allow this platform to load."""
    with patch("homeassistant.components.nibe_heatpump.PLATFORMS", [Platform.CLIMATE]):
        yield


def _setup_climate_group(
    coils: dict[int, Any], model: Model, climate_id: str
) -> tuple[ClimateCoilGroup, UnitCoilGroup]:
    """Initialize coils for a climate group, with some default values."""
    climate = CLIMATE_COILGROUPS[model.series][climate_id]
    unit = UNIT_COILGROUPS[model.series]["main"]

    if climate.active_accessory is not None:
        coils[climate.active_accessory] = "ON"
    coils[climate.current] = 20.5
    coils[climate.setpoint_heat] = 21.0
    coils[climate.setpoint_cool] = 30.0
    coils[climate.mixing_valve_state] = 20
    coils[climate.use_room_sensor] = "ON"
    coils[unit.prio] = "OFF"
    coils[unit.cooling_with_room_sensor] = "ON"

    return climate, unit


@pytest.mark.parametrize(
    ("model", "climate_id", "entity_id"),
    [
        (Model.S320, "s1", "climate.climate_system_s1"),
        (Model.F1155, "s2", "climate.climate_system_s2"),
    ],
)
async def test_basic(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    model: Model,
    climate_id: str,
    entity_id: str,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting of value."""
    climate, unit = _setup_climate_group(coils, model, climate_id)

    await async_add_model(hass, model)

    assert hass.states.get(entity_id) == snapshot(name="initial")

    mock_connection.mock_coil_update(unit.prio, "COOLING")
    assert hass.states.get(entity_id) == snapshot(name="cooling")

    mock_connection.mock_coil_update(unit.prio, "HEAT")
    assert hass.states.get(entity_id) == snapshot(name="heating")

    mock_connection.mock_coil_update(climate.mixing_valve_state, 30)
    assert hass.states.get(entity_id) == snapshot(name="idle (mixing valve)")

    mock_connection.mock_coil_update(climate.mixing_valve_state, 20)
    mock_connection.mock_coil_update(unit.cooling_with_room_sensor, "OFF")
    assert hass.states.get(entity_id) == snapshot(name="heating (only)")

    mock_connection.mock_coil_update(climate.use_room_sensor, "OFF")
    assert hass.states.get(entity_id) == snapshot(name="heating (auto)")

    mock_connection.mock_coil_update(unit.prio, None)
    assert hass.states.get(entity_id) == snapshot(name="off (auto)")

    coils.clear()
    assert hass.states.get(entity_id) == snapshot(name="unavailable")


@pytest.mark.parametrize(
    ("model", "climate_id", "entity_id"),
    [
        (Model.F1155, "s2", "climate.climate_system_s2"),
        (Model.F1155, "s3", "climate.climate_system_s3"),
    ],
)
async def test_active_accessory(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    model: Model,
    climate_id: str,
    entity_id: str,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate groups that can be deactivated by configuration."""
    climate, unit = _setup_climate_group(coils, model, climate_id)

    await async_add_model(hass, model)

    assert hass.states.get(entity_id) == snapshot(name="initial")

    mock_connection.mock_coil_update(climate.active_accessory, "OFF")
    assert hass.states.get(entity_id) == snapshot(name="unavailable (not supported)")


@pytest.mark.parametrize(
    ("model", "climate_id", "entity_id"),
    [
        (Model.S320, "s1", "climate.climate_system_s1"),
        (Model.F1155, "s2", "climate.climate_system_s2"),
    ],
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    model: Model,
    climate_id: str,
    entity_id: str,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setting temperature."""
    climate, _ = _setup_climate_group(coils, model, climate_id)

    await async_add_model(hass, model)

    coil_setpoint_heat = mock_connection.heatpump.get_coil_by_address(
        climate.setpoint_heat
    )
    coil_setpoint_cool = mock_connection.heatpump.get_coil_by_address(
        climate.setpoint_cool
    )

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 22,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_connection.write_coil.mock_calls == [
        call(CoilData(coil_setpoint_heat, 22))
    ]
    mock_connection.write_coil.reset_mock()

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: 22,
            ATTR_HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_connection.write_coil.mock_calls == [
        call(CoilData(coil_setpoint_cool, 22))
    ]
    mock_connection.write_coil.reset_mock()

    with pytest.raises(ValueError):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TEMPERATURE: 22,
            },
            blocking=True,
        )

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_HIGH: 30,
            ATTR_TARGET_TEMP_LOW: 22,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_connection.write_coil.mock_calls == [
        call(CoilData(coil_setpoint_heat, 22)),
        call(CoilData(coil_setpoint_cool, 30)),
    ]

    mock_connection.write_coil.reset_mock()


@pytest.mark.parametrize(
    ("hvac_mode", "cooling_with_room_sensor", "use_room_sensor"),
    [
        (HVACMode.HEAT_COOL, "ON", "ON"),
        (HVACMode.HEAT, "OFF", "ON"),
        (HVACMode.AUTO, "OFF", "OFF"),
    ],
)
@pytest.mark.parametrize(
    ("model", "climate_id", "entity_id"),
    [
        (Model.S320, "s1", "climate.climate_system_s1"),
        (Model.F1155, "s2", "climate.climate_system_s2"),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    model: Model,
    climate_id: str,
    entity_id: str,
    cooling_with_room_sensor: str,
    use_room_sensor: str,
    hvac_mode: HVACMode,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
) -> None:
    """Test setting a hvac mode."""
    climate, unit = _setup_climate_group(coils, model, climate_id)

    await async_add_model(hass, model)

    coil_use_room_sensor = mock_connection.heatpump.get_coil_by_address(
        climate.use_room_sensor
    )
    coil_cooling_with_room_sensor = mock_connection.heatpump.get_coil_by_address(
        unit.cooling_with_room_sensor
    )

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HVAC_MODE: hvac_mode,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_connection.write_coil.mock_calls == [
        call(CoilData(coil_cooling_with_room_sensor, cooling_with_room_sensor)),
        call(CoilData(coil_use_room_sensor, use_room_sensor)),
    ]


@pytest.mark.parametrize(
    ("model", "climate_id", "entity_id"),
    [
        (Model.S320, "s1", "climate.climate_system_s1"),
        (Model.F1155, "s2", "climate.climate_system_s2"),
    ],
)
async def test_set_invalid_hvac_mode(
    hass: HomeAssistant,
    mock_connection: MockConnection,
    model: Model,
    climate_id: str,
    entity_id: str,
    coils: dict[int, Any],
    entity_registry_enabled_by_default: None,
) -> None:
    """Test setting an invalid hvac mode."""
    _setup_climate_group(coils, model, climate_id)

    await async_add_model(hass, model)

    with pytest.raises(ValueError):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    assert mock_connection.write_coil.mock_calls == []
