"""Tests for Comelit SimpleHome climate platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

from aiocomelit.api import ComelitSerialBridgeObject
from aiocomelit.const import CLIMATE, WATT
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
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
        snapshot(exclude=props("unique_id")),
        mock_serial_bridge_config_entry.entry_id,
    )


@pytest.mark.parametrize(
    "val",
    [
        [
            [270, 0, "U", "M", 50, 0, 0, "U"],
            [650, 0, "O", "M", 500, 0, 0, "N"],
            [0, 0],
        ],
        [
            [270, 1, "O", "A", 50, 1, 0, "O"],
            [650, 1, "O", "A", 500, 1, 0, "N"],
            [0, 0],
        ],
    ],
)
async def test_climate_data_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    val: list[Any, Any],
) -> None:
    """Test climate data update."""
    await setup_integration(hass, mock_serial_bridge_config_entry)

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.state == HVACAction.HEATING
    assert entity.attributes[ATTR_TEMPERATURE] == 21.1

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

    freezer.tick(SCAN_INTERVAL + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.state == HVACAction.HEATING
    assert entity.attributes[ATTR_TEMPERATURE] == 27


async def test_climate_set_temperature(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test climate set temperature service."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.state == HVACMode.HEAT
    assert entity.attributes[ATTR_TEMPERATURE] == 21.1

    # Test set temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 23},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.state == HVACMode.HEAT
    assert entity.attributes[ATTR_TEMPERATURE] == 23


async def test_climate_hvac_mode(
    hass: HomeAssistant,
    mock_serial_bridge: AsyncMock,
    mock_serial_bridge_config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test climate hvac mode service."""

    await setup_integration(hass, mock_serial_bridge_config_entry)

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.state == HVACMode.HEAT
    assert entity.attributes[ATTR_TEMPERATURE] == 21.1

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    mock_serial_bridge.set_clima_status.assert_called()

    entity = hass.states.get(ENTITY_ID)
    assert entity
    assert entity.state == HVACMode.OFF
