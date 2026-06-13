"""Binary sensor platform tests for iAquaLink."""

from __future__ import annotations

from unittest.mock import AsyncMock

from iaqualink.client import AqualinkClient
from iaqualink.systems.iaqua.device import IaquaBinarySensor
from iaqualink.systems.iaqua.system import IaquaSystem
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    """Test all binary sensor entities are created correctly."""
    await assert_platform_setup(
        hass, config_entry, client, entity_registry, snapshot, BINARY_SENSOR_DOMAIN
    )


async def _setup_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    *,
    name: str,
    state: str,
) -> str:
    """Set up the integration with a single binary sensor entity."""
    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    sensor = get_aqualink_device(
        system, name=name, cls=IaquaBinarySensor, data={"state": state}
    )
    system.get_devices = AsyncMock(return_value={sensor.name: sensor})
    await setup_entry(hass, config_entry, system)

    entity_ids = hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)
    assert len(entity_ids) == 1
    return entity_ids[0]


@pytest.mark.parametrize(
    ("name", "expected_class"),
    [
        pytest.param("freeze_protection", BinarySensorDeviceClass.COLD, id="freeze"),
        pytest.param("auxiliary", None, id="default"),
    ],
)
async def test_binary_sensor_device_class(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    entity_registry: er.EntityRegistry,
    name: str,
    expected_class: BinarySensorDeviceClass | None,
) -> None:
    """Test binary sensor device class mapping."""
    entity_id = await _setup_binary_sensor(
        hass,
        config_entry,
        client,
        name=name,
        state="1",
    )

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.original_device_class == expected_class
    assert entry.has_entity_name is True

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_binary_sensor_off_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test binary sensor off state is exposed through Home Assistant."""
    entity_id = await _setup_binary_sensor(
        hass,
        config_entry,
        client,
        name="freeze_protection",
        state="0",
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
