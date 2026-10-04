"""Tests for the Daikin Onecta climate platform."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
    HVACMode,
)
from homeassistant.components.daikin_onecta.climate import DaikinClimate
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import DOMAIN

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("last_update_success", "device_available", "expected"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_climate_availability(
    last_update_success: bool, device_available: bool, expected: bool
) -> None:
    """Climate entities require a successful update and an available device."""
    entity = object.__new__(DaikinClimate)
    entity.coordinator = MagicMock(last_update_success=last_update_success)
    entity._device = MagicMock(available=device_available)

    assert entity.available is expected


async def test_set_temperature_updates_cached_setpoint_and_siblings() -> None:
    """Update the cached setpoint and notify sibling climates after a write."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    coordinator = MagicMock()
    device.patch = AsyncMock(return_value=True)
    setpoint = MagicMock(value=20)
    object.__setattr__(entity, "_device", device)
    entity.coordinator = coordinator
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_setpoint", "roomTemperature")
    object.__setattr__(entity, "_attr_target_temperature", 20)
    entity.operation_mode = MagicMock(return_value=MagicMock(value="heating"))
    entity.setpoint = MagicMock(return_value=setpoint)
    await entity.async_set_temperature(temperature=21)

    assert setpoint.value == 21
    coordinator.async_update_listeners.assert_called_once_with()


async def test_enable_boost_stops_after_failed_turn_on() -> None:
    """Do not enable boost when the prerequisite turn-on fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    device.patch = AsyncMock(return_value=True)
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.OFF)
    entity.async_turn_on = AsyncMock()

    assert not await entity._async_enable_preset_mode(PRESET_BOOST)

    entity.async_turn_on.assert_awaited_once()
    device.patch.assert_not_awaited()


async def test_climate_service_updates_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test climate services through the Home Assistant integration API."""
    setpoint = SimpleNamespace(
        value=20, min_value=7, max_value=30, step_value=1, settable=True
    )
    operation_mode = SimpleNamespace(value="heating", values=["heating"], settable=True)
    climate_control = MagicMock(embedded_id="zone")
    climate_control.temperature_control = SimpleNamespace(
        value=SimpleNamespace(
            operation_modes={
                "heating": SimpleNamespace(setpoints={"roomTemperature": setpoint})
            }
        )
    )
    climate_control.operation_mode = operation_mode
    climate_control.on_off_mode = SimpleNamespace(value="on")
    climate_control.fan_control = None
    climate_control.holiday_mode = None
    climate_control.sensory_data = None
    climate_control.characteristic.return_value = None

    device = MagicMock(id="gateway", name="Daikin", available=True)
    device.device = SimpleNamespace(
        device_model="Daikin",
        management_points_by_type=lambda _: (climate_control,),
    )
    device.management_point.return_value = climate_control
    device.patch = AsyncMock(return_value=True)

    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    coordinator.data = {device.id: device}
    coordinator.last_update_success = True
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "gateway_zone_roomTemperature"
    )
    assert entity_id is not None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[ATTR_TEMPERATURE] == 21
    device.patch.assert_awaited_once_with(
        "gateway",
        "zone",
        "temperatureControl",
        "/operationModes/heating/setpoints/roomTemperature",
        21,
    )


@pytest.mark.parametrize(
    "ignore_missing_translations", [["component.climate.services."]]
)
async def test_setup_creates_entities_per_management_point(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up a separate climate entity for each climate-control zone."""
    coordinator = MagicMock()
    gateway = MagicMock(id="device", device_model="Daikin")
    onecta_device = MagicMock(id="device", device=gateway)
    coordinator.data = {"device": onecta_device}
    first_zone = MagicMock(embedded_id="first_zone")
    first_zone.temperature_control.value.operation_modes = {
        "heating": MagicMock(setpoints={"roomTemperature": MagicMock()}),
    }
    second_zone = MagicMock(embedded_id="second_zone")
    second_zone.temperature_control.value.operation_modes = {
        "cooling": MagicMock(setpoints={"roomTemperature": MagicMock()}),
    }
    gateway.management_points_by_type.return_value = (first_zone, second_zone)
    coordinator.async_config_entry_first_refresh = AsyncMock()

    class TestClimateEntity(ClimateEntity):
        """Minimal climate entity used to observe platform setup."""

        def __init__(
            self,
            device: MagicMock,
            setpoint: str,
            coordinator: MagicMock,
            embedded_id: str,
        ) -> None:
            """Initialize the test entity."""
            self._attr_unique_id = f"{device.id}_{embedded_id}_{setpoint}"
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_hvac_modes = [HVACMode.OFF]

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.daikin_onecta.climate.DaikinClimate",
            TestClimateEntity,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_first_zone_roomTemperature"
    )
    assert entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_second_zone_roomTemperature"
    )
