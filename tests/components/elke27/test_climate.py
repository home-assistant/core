"""Tests for Elke27 thermostats."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_ON,
    HVACMode,
)
from homeassistant.components.elke27 import climate as climate_module
from homeassistant.components.elke27.climate import async_setup_entry
from homeassistant.components.elke27.coordinator import Elke27DataUpdateCoordinator
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


class _Hub:
    def __init__(self) -> None:
        self.is_ready = True
        self.panel_name = None
        self.async_set_tstat_status = AsyncMock(return_value=True)


async def test_climate_entities_updates_and_actions(hass: HomeAssistant) -> None:
    """Test climate entities are created and delegate actions."""
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.65"})
    entry.add_to_hass(hass)

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(
        panel_info=SimpleNamespace(
            mac="aa:bb:cc:dd:ee:ff",
            name="Panel A",
            serial="1234",
        ),
        thermostats=[
            SimpleNamespace(
                tstat_id=1,
                name="Main",
                temperature=71,
                heat_setpoint=68,
                cool_setpoint=74,
                mode="AUTO",
                fan_mode="AUTO",
            )
        ],
    )
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[climate_module.Elke27Thermostat] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert len(entities) == 1

    thermostat = entities[0]
    assert thermostat.hvac_mode is HVACMode.HEAT_COOL
    assert thermostat.current_temperature == 71
    assert thermostat.target_temperature_low == 68
    assert thermostat.target_temperature_high == 74

    await thermostat.async_set_hvac_mode(HVACMode.COOL)
    hub.async_set_tstat_status.assert_awaited_with(1, mode="COOL")

    await thermostat.async_set_fan_mode(FAN_ON)
    hub.async_set_tstat_status.assert_awaited_with(1, fan_mode="ON")

    await thermostat.async_set_temperature(
        **{ATTR_TARGET_TEMP_LOW: 67, ATTR_TARGET_TEMP_HIGH: 75}
    )
    hub.async_set_tstat_status.assert_awaited_with(
        1, heat_setpoint=67, cool_setpoint=75
    )

    snapshot.thermostats[0].mode = "HEAT"
    coordinator.async_set_updated_data(snapshot)
    await hass.async_block_till_done()
    assert thermostat.hvac_mode is HVACMode.HEAT


def test_climate_temperature_normalization() -> None:
    """Verify thermostat temperatures with implied decimals are normalized."""
    assert climate_module._normalize_temperature(806) == 80.6
    assert climate_module._normalize_temperature(71) == 71.0
    assert climate_module._normalize_temperature(None) is None


async def test_climate_pin_required(hass: HomeAssistant) -> None:
    """Test PIN-required error surfaces as HomeAssistantError."""
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.66"})
    entry.add_to_hass(hass)

    hub = _Hub()
    hub.async_set_tstat_status.side_effect = climate_module.Elke27PinRequiredError

    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    snapshot = SimpleNamespace(thermostats=[SimpleNamespace(tstat_id=1, mode="OFF")])
    coordinator.async_set_updated_data(snapshot)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)

    entities: list[climate_module.Elke27Thermostat] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    thermostat = entities[0]

    with pytest.raises(
        HomeAssistantError, match="PIN required to perform this action."
    ):
        await thermostat.async_set_hvac_mode(HVACMode.HEAT)


async def test_climate_setup_edge_cases(hass: HomeAssistant) -> None:
    """Verify setup handles missing runtime data and snapshots."""
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.67"})
    entry.add_to_hass(hass)
    entry.runtime_data = None

    entities: list[climate_module.Elke27Thermostat] = []

    def _add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    hub = _Hub()
    coordinator = Elke27DataUpdateCoordinator(hass, hub, entry)
    coordinator.async_set_updated_data(None)
    entry.runtime_data = Elke27RuntimeData(hub=hub, coordinator=coordinator)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    snapshot = SimpleNamespace(thermostats=[])
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []

    snapshot.thermostats = [SimpleNamespace(tstat_id="x", name="Bad")]
    coordinator.async_set_updated_data(snapshot)
    await async_setup_entry(hass, entry, _add_entities)
    assert entities == []


def test_climate_properties_when_missing() -> None:
    """Verify properties handle missing thermostat data."""
    hub = _Hub()
    coordinator = SimpleNamespace(data=None)
    entry = MockConfigEntry(domain="elke27", data={CONF_HOST: "192.168.1.68"})
    thermostat = climate_module.Elke27Thermostat(
        coordinator, hub, entry, 1, SimpleNamespace()
    )
    assert thermostat.current_temperature is None
    hub.is_ready = False
    assert thermostat.available is False
    assert thermostat.current_temperature is None


def test_climate_iter_tstats_variants() -> None:
    """Verify thermostat iteration for mapping and list."""
    assert list(climate_module._iter_tstats({"thermostats": {1: "x"}})) == []
    snapshot = SimpleNamespace(thermostats={1: "x"})
    assert list(climate_module._iter_tstats(snapshot)) == ["x"]
    snapshot.thermostats = ["a"]
    assert list(climate_module._iter_tstats(snapshot)) == ["a"]
    snapshot.thermostats = "bad"
    assert list(climate_module._iter_tstats(snapshot)) == []
