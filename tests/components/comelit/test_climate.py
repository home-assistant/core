"""Tests for Comelit SimpleHome climate platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE, WATT
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.comelit.const import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "climate.climate0"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.comelit.BRIDGE_PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_serial_bridge_config_entry)

    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_serial_bridge_config_entry.entry_id,
    )


@pytest.mark.parametrize(
    ("val", "mode", "temp"),
    [
        (
            [
                [100, 0, "U", "M", 210, 0, 0, "U"],
                [650, 0, "O", "M", 500, 0, 0, "N"],
                [0, 0],
            ],
            HVACMode.HEAT,
            21.0,
        ),
        (
            [
                [100, 1, "U", "A", 210, 1, 0, "O"],
                [650, 0, "O", "M", 500, 0, 0, "N"],
                [0, 0],
            ],
            HVACMode.HEAT,
            21.0,
        ),
        (
            [
                [100, 0, "O", "A", 210, 0, 0, "O"],
                [650, 0, "O", "M", 500, 0, 0, "N"],
                [0, 0],
            ],
            HVACMode.OFF,
            21.0,
        ),
    ],
)
async def test_climate_data_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    val: list[Any, Any],
    mode: HVACMode,
    temp: float,
) -> None:
    """Test climate data update."""
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0

    mock_serial_bridge.get_all_devices.return_value[CLIMATE] = {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Climate0",
            status=0,
            human_status="off",
            type="climate",
            val=val,
            protected=0,
            zone="Living room",
            power=0.0,
            power_unit=WATT,
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == mode
    assert state.attributes[ATTR_TEMPERATURE] == temp


async def test_climate_data_update_bad_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test climate data update."""
    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0

    mock_serial_bridge.get_all_devices.return_value[CLIMATE] = {
        0: ComelitSerialBridgeObject(
            index=0,
            name="Climate0",
            status=0,
            human_status="off",
            type="climate",
            val="bad_data",
            protected=0,
            zone="Living room",
            power=0.0,
            power_unit=WATT,
        ),
    }

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0


async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test climate set temperature service."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0

    # Test set temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 23},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 23.0


async def test_climate_set_temperature_when_off(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test climate set temperature service when off."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0

    # Switch climate off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.OFF

    # Test set temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 23},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.OFF


async def test_climate_hvac_mode(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test climate hvac mode service."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.OFF


async def test_climate_hvac_mode_when_off(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
) -> None:
    """Test climate hvac mode service when off."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 5.0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.AUTO
