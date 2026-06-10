"""Sensor platform tests for iAquaLink."""

from __future__ import annotations

from unittest.mock import AsyncMock

from iaqualink.client import AqualinkClient
from iaqualink.systems.iaqua.device import IaquaSensor
from iaqualink.systems.iaqua.system import IaquaSystem
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.const import STATE_UNKNOWN, UnitOfTemperature
from homeassistant.core import HomeAssistant
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
    """Test all sensor entities are created correctly."""
    await assert_platform_setup(
        hass, config_entry, client, entity_registry, snapshot, SENSOR_DOMAIN
    )


async def _setup_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    *,
    name: str,
    state: str,
    temp_unit: str = "F",
) -> tuple[str, object]:
    """Set up the integration with a single sensor entity."""
    system = get_aqualink_system(
        client,
        cls=IaquaSystem,
        data={"home_screen": [{}, {}, {}, {"temp_scale": temp_unit}]},
    )
    system.online = True

    async def update() -> None:
        system.temp_unit = temp_unit

    system.update = AsyncMock(side_effect=update)
    sensor = get_aqualink_device(
        system, name=name, cls=IaquaSensor, data={"state": state}
    )
    system.get_devices = AsyncMock(return_value={sensor.name: sensor})

    await setup_entry(hass, config_entry, system)

    entity_ids = hass.states.async_entity_ids(SENSOR_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    return entity_id, entity_state


@pytest.mark.parametrize(
    ("name", "temp_unit", "expected_class", "expected_unit"),
    [
        pytest.param(
            "pool_temp",
            "F",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.FAHRENHEIT,
            id="fahrenheit-temperature",
        ),
        pytest.param(
            "spa_temp",
            "C",
            SensorDeviceClass.TEMPERATURE,
            UnitOfTemperature.CELSIUS,
            id="celsius-temperature",
        ),
        pytest.param("ph", "F", None, None, id="non-temperature"),
    ],
)
async def test_sensor_initialization(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    name: str,
    temp_unit: str,
    expected_class: SensorDeviceClass | None,
    expected_unit: UnitOfTemperature | None,
) -> None:
    """Test sensor initialization for temperature and generic sensors."""
    if expected_unit is UnitOfTemperature.FAHRENHEIT:
        hass.config.units = US_CUSTOMARY_SYSTEM

    _, entity_state = await _setup_sensor(
        hass,
        config_entry,
        client,
        name=name,
        temp_unit=temp_unit,
        state="72",
    )

    assert entity_state.attributes.get("device_class") == expected_class
    assert entity_state.attributes.get("unit_of_measurement") == expected_unit


@pytest.mark.parametrize(
    ("state", "expected_state"),
    [
        pytest.param("", STATE_UNKNOWN, id="empty"),
        pytest.param("72", "72", id="int"),
        pytest.param("7.2", "7.2", id="float"),
    ],
)
async def test_sensor_native_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    state: str,
    expected_state: str,
) -> None:
    """Test sensor state parsing."""
    _, entity_state = await _setup_sensor(
        hass,
        config_entry,
        client,
        name="ph",
        state=state,
    )

    assert entity_state.state == expected_state
