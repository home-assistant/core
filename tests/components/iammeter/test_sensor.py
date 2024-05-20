"""Tests for the Iammeter sensor platform."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, assert_setup_component

MOCKSN = "MOCKSN123"
SENSOR_NAME = "MockName"
NAME_LIST = [
    "Voltage",
    "Current",
    "Power",
    "ImportEnergy",
    "ExportGrid",
    "Frequency",
    "PF",
]
PHASE_LIST = ["A", "B", "C", "NET"]

MOCK_CONFIG = {"name": SENSOR_NAME, "host": "127.0.0.1", "port": 80}
SENSOR_CONFIG = {
    "sensor": [
        {
            "platform": DOMAIN,
            "name": SENSOR_NAME,
            "host": "127.0.0.1",
            "port": 80,
        },
    ]
}


@pytest.fixture(name="mockIammeter_3080")
def mock_3080_controller() -> Generator[Mock]:
    """Mock a successful IamMeter API."""
    api = Mock()
    api.get_data.return_value = {
        "sn": MOCKSN,
        "Model": "WEM3080",
        "Data": [1, 2, 3, 4, 5],
    }
    with patch("iammeter.client.Client", return_value=api):
        yield api


@pytest.fixture(name="mockIammeter_3080T")
def mock_3080T_controller() -> Generator[Mock]:
    """Mock a successful IamMeter API."""
    api = Mock()
    api.get_data.return_value = {
        "sn": MOCKSN,
        "Model": "WEM3080T",
        "Data": [[1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7]],
    }
    with patch("iammeter.client.Client", return_value=api):
        yield api

@pytest.mark.usefixtures("mockIammeter_3080")
async def test_unique_id_migration_3080(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor ID migration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    id_phase_range = 1
    id_name_range = 5
    for row in range(id_phase_range):
        for idx in range(id_name_range):
            old_unique_id = f"{MOCKSN}-{row}-{idx}"
            # Add a sensor with an old unique_id to the entity registry
            entity_entry = entity_registry.async_get_or_create(
                DOMAIN,
                Platform.SENSOR,
                old_unique_id,
                suggested_object_id=SENSOR_NAME,
                config_entry=entry,
                original_name=SENSOR_NAME,
            )
            ent_reg = er.async_get(hass)
            entity_id = ent_reg.async_get_entity_id(
                DOMAIN, Platform.SENSOR, old_unique_id
            )
            assert entity_entry.unique_id == old_unique_id
    with assert_setup_component(1, Platform.SENSOR):
        assert await async_setup_component(
            hass,
            Platform.SENSOR,
            SENSOR_CONFIG,
        )
        await hass.async_block_till_done()
    for row in range(id_phase_range):
        for idx in range(id_name_range):
            old_unique_id = f"{MOCKSN}-{row}-{idx}"
            entity_id = ent_reg.async_get_entity_id(
                DOMAIN, Platform.SENSOR, old_unique_id
            )
            assert entity_id is None
            new_unique_id = f"{MOCKSN}_{NAME_LIST[idx]}"
            entity_id = ent_reg.async_get_entity_id(
                DOMAIN, Platform.SENSOR, new_unique_id
            )
            assert entity_id is not None


@pytest.mark.usefixtures("mockIammeter_3080T")
async def test_unique_id_migration_3080T(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor ID migration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    id_phase_range = 4
    id_name_range = 7
    for row in range(id_phase_range):
        for idx in range(id_name_range):
            old_unique_id = f"{MOCKSN}-{row}-{idx}"
            # Add a sensor with an old unique_id to the entity registry
            entity_entry = entity_registry.async_get_or_create(
                DOMAIN,
                Platform.SENSOR,
                old_unique_id,
                suggested_object_id=SENSOR_NAME,
                config_entry=entry,
                original_name=SENSOR_NAME,
            )
            ent_reg = er.async_get(hass)
            entity_id = ent_reg.async_get_entity_id(
                DOMAIN, Platform.SENSOR, old_unique_id
            )
            assert entity_entry.unique_id == old_unique_id
    with assert_setup_component(1, Platform.SENSOR):
        assert await async_setup_component(
            hass,
            Platform.SENSOR,
            SENSOR_CONFIG,
        )
        await hass.async_block_till_done()
    for row in range(id_phase_range):
        for idx in range(id_name_range):
            old_unique_id = f"{MOCKSN}-{row}-{idx}"
            entity_id = ent_reg.async_get_entity_id(
                DOMAIN, Platform.SENSOR, old_unique_id
            )
            assert entity_id is None
            new_unique_id = f"{MOCKSN}_{NAME_LIST[idx]}_{PHASE_LIST[row]}"
            entity_id = ent_reg.async_get_entity_id(
                DOMAIN, Platform.SENSOR, new_unique_id
            )
            assert entity_id is not None
