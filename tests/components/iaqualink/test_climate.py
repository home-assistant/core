"""Climate platform tests for iAquaLink."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.systems.iaqua.device import (
    AqualinkState,
    IaquaAuxSwitch,
    IaquaSensor,
    IaquaThermostat,
)
from iaqualink.systems.iaqua.system import IaquaSystem
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import (
    assert_platform_setup,
    get_aqualink_device,
    get_aqualink_system,
    setup_entry,
)

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all climate entities are created correctly."""
    await assert_platform_setup(
        hass, config_entry, client, entity_registry, snapshot, CLIMATE_DOMAIN
    )


async def _setup_thermostat(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    *,
    temp_unit: str = "F",
    heater_state: str = AqualinkState.ON.value,
    target_temperature: str = "84",
    current_temperature: str = "80",
) -> tuple[IaquaSystem, object, object, object, str, object]:
    """Set up the integration with a single thermostat entity."""
    if temp_unit == "F":
        hass.config.units = US_CUSTOMARY_SYSTEM

    system = get_aqualink_system(
        client,
        cls=IaquaSystem,
        data={"home_screen": [{}, {}, {}, {"temp_scale": temp_unit}]},
    )
    system.online = True

    async def update() -> None:
        system.temp_unit = temp_unit

    system.update = AsyncMock(side_effect=update)
    heater = get_aqualink_device(
        system,
        name="pool_heater",
        cls=IaquaAuxSwitch,
        data={"state": heater_state, "aux": "1"},
    )
    sensor = get_aqualink_device(
        system,
        name="pool_temp",
        cls=IaquaSensor,
        data={"state": current_temperature},
    )
    thermostat = get_aqualink_device(
        system,
        name="pool_set_point",
        cls=IaquaThermostat,
        data={"state": target_temperature},
    )
    system.devices = {
        heater.name: heater,
        sensor.name: sensor,
        thermostat.name: thermostat,
    }
    system.get_devices = AsyncMock(return_value={thermostat.name: thermostat})
    system.set_aux = AsyncMock()
    system.set_temps = AsyncMock()

    await setup_entry(hass, config_entry, system)

    entity_ids = hass.states.async_entity_ids(CLIMATE_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    return system, heater, sensor, thermostat, entity_id, entity_state


@pytest.mark.parametrize(
    ("heater_state", "expected_action", "expected_mode"),
    [
        pytest.param(
            AqualinkState.ON.value, HVACAction.HEATING, HVACMode.HEAT, id="heating"
        ),
        pytest.param(
            AqualinkState.ENABLED.value, HVACAction.IDLE, HVACMode.OFF, id="idle"
        ),
        pytest.param(AqualinkState.OFF.value, HVACAction.OFF, HVACMode.OFF, id="off"),
    ],
)
async def test_thermostat_properties(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    heater_state: str,
    expected_action: HVACAction,
    expected_mode: HVACMode,
) -> None:
    """Test thermostat properties and HVAC action mapping."""
    _, _, _, _, _, entity_state = await _setup_thermostat(
        hass,
        config_entry,
        client,
        heater_state=heater_state,
    )

    assert entity_state.state == expected_mode
    assert entity_state.attributes["hvac_action"] == expected_action
    assert entity_state.attributes["temperature"] == 84.0
    assert entity_state.attributes["current_temperature"] == 80.0


async def test_thermostat_current_temperature_none(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test thermostat current temperature handles empty values."""
    _, _, _, _, _, entity_state = await _setup_thermostat(
        hass,
        config_entry,
        client,
        temp_unit="C",
        heater_state=AqualinkState.OFF.value,
        target_temperature="24",
        current_temperature="",
    )

    assert entity_state.state == HVACMode.OFF
    assert entity_state.attributes["current_temperature"] is None


@pytest.mark.parametrize(
    ("hvac_mode", "initial_state", "expected_state"),
    [
        pytest.param(HVACMode.HEAT, AqualinkState.OFF.value, HVACMode.HEAT, id="heat"),
        pytest.param(HVACMode.OFF, AqualinkState.ON.value, HVACMode.OFF, id="off"),
    ],
)
async def test_thermostat_set_hvac_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    hvac_mode: HVACMode,
    initial_state: str,
    expected_state: HVACMode,
) -> None:
    """Test thermostat HVAC mode service updates Home Assistant state."""
    system, heater, _, _, entity_id, _ = await _setup_thermostat(
        hass,
        config_entry,
        client,
        heater_state=initial_state,
    )

    async def set_aux(_: str) -> None:
        heater.data["state"] = (
            AqualinkState.ON.value
            if hvac_mode == HVACMode.HEAT
            else AqualinkState.OFF.value
        )

    system.set_aux = AsyncMock(side_effect=set_aux)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == expected_state


async def test_thermostat_set_temperature(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test thermostat target temperature service updates Home Assistant state."""
    system, _, _, thermostat, entity_id, _ = await _setup_thermostat(
        hass,
        config_entry,
        client,
    )

    async def set_temps(data: dict[str, str]) -> None:
        thermostat.data["state"] = data["temp1"]

    system.set_temps = AsyncMock(side_effect=set_temps)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 84.9},
        blocking=True,
    )

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.attributes["temperature"] == 84.0


@pytest.mark.parametrize(
    ("service", "service_data", "system_attr"),
    [
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            "set_aux",
            id="set-hvac-mode",
        ),
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 84},
            "set_temps",
            id="set-temperature",
        ),
    ],
)
@pytest.mark.parametrize(
    ("raised_exception", "expected_exception", "match"),
    [
        pytest.param(
            AqualinkServiceException,
            HomeAssistantError,
            "Aqualink error: AqualinkServiceException",
            id="service",
        ),
        pytest.param(
            TimeoutError(),
            HomeAssistantError,
            "Aqualink error: TimeoutError",
            id="timeout",
        ),
        pytest.param(
            httpx.HTTPError("boom"),
            HomeAssistantError,
            "Aqualink error: boom",
            id="http",
        ),
        pytest.param(
            AqualinkServiceUnauthorizedException,
            ConfigEntryAuthFailed,
            "Invalid credentials for iAquaLink",
            id="unauthorized",
        ),
    ],
)
async def test_climate_action_errors_leave_state_unchanged(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    service: str,
    service_data: dict[str, Any],
    system_attr: str,
    raised_exception: Exception | type[Exception],
    expected_exception: type[Exception],
    match: str,
) -> None:
    """Test climate action errors are surfaced through the service call."""
    system, _, _, _, entity_id, entity_state = await _setup_thermostat(
        hass,
        config_entry,
        client,
        heater_state=AqualinkState.OFF.value,
    )
    initial_state = entity_state.state
    setattr(system, system_attr, AsyncMock(side_effect=raised_exception))

    with pytest.raises(expected_exception, match=match):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == initial_state


async def test_thermostat_set_unknown_hvac_mode_logs_warning(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unsupported HVAC modes log a warning and keep state unchanged."""
    system, _, _, _, entity_id, _ = await _setup_thermostat(
        hass,
        config_entry,
        client,
        heater_state=AqualinkState.OFF.value,
    )
    climate_component = hass.data[CLIMATE_DOMAIN]
    entity = climate_component.get_entity(entity_id)
    assert entity is not None

    with caplog.at_level(logging.WARNING):
        await entity.async_set_hvac_mode(HVACMode.COOL)

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == HVACMode.OFF
    assert "Unknown operation mode" in caplog.text
    system.set_aux.assert_not_called()
