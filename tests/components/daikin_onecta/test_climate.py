"""Tests for the Daikin Onecta climate platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.climate import ClimateEntity, HVACMode
from homeassistant.components.daikin_onecta.climate import DaikinClimate
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform, UnitOfTemperature
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


async def test_set_temperature_updates_cached_setpoint() -> None:
    """Update the cached setpoint after a successful cloud write."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    device.patch = AsyncMock(return_value=True)
    setpoint = MagicMock(value=20)
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_setpoint", "roomTemperature")
    object.__setattr__(entity, "_attr_target_temperature", 20)
    entity.operation_mode = MagicMock(return_value=MagicMock(value="heating"))
    entity.setpoint = MagicMock(return_value=setpoint)
    entity.async_write_ha_state = MagicMock()

    await entity.async_set_temperature(temperature=21)

    assert setpoint.value == 21


@pytest.mark.parametrize(
    "ignore_missing_translations", [["component.climate.services."]]
)
async def test_setup_creates_entities_per_management_point(
    hass: HomeAssistant, config_entry: MockConfigEntry
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

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_first_zone_roomTemperature"
    )
    assert registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_second_zone_roomTemperature"
    )
