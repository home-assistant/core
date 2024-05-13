"""Tests for the Iammeter sensor platform."""

from unittest.mock import Mock, patch

import pytest

from homeassistant.components.iammeter.const import DEVICE_3080, DEVICE_3080T, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, assert_setup_component

MOCKSN = "MOCKSN123"
SENSOR_NAME = "MockName"
name_list = [
    "Voltage",
    "Current",
    "Power",
    "ImportEnergy",
    "ExportGrid",
    "Frequency",
    "PF",
]
phase_list = ["A", "B", "C", "NET"]

mock_config = {"name": SENSOR_NAME, "host": "127.0.0.1", "port": 80}
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
def mock_controller1():
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
def mock_controller2():
    """Mock a successful IamMeter API."""
    api = Mock()
    api.get_data.return_value = {
        "sn": MOCKSN,
        "Model": "WEM3080T",
        "Data": [[1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7]],
    }
    with patch("iammeter.client.Client", return_value=api):
        yield api


async def test_unique_id_migration_3080(
    mockIammeter_3080,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor ID migration."""
    entry = MockConfigEntry(domain=DOMAIN, data=mock_config)
    entry.add_to_hass(hass)
    model = DEVICE_3080
    id_phase_range = 1 if model == DEVICE_3080 else 4
    id_name_range = 5 if model == DEVICE_3080 else 7
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
                new_unique_id = (
                    f"{MOCKSN}_{name_list[idx]}"
                    if model == DEVICE_3080
                    else f"{MOCKSN}_{name_list[idx]}_{phase_list[row]}"
                )
                entity_id = ent_reg.async_get_entity_id(
                    DOMAIN, Platform.SENSOR, new_unique_id
                )
                assert entity_id is not None


async def test_unique_id_migration_3080T(
    mockIammeter_3080T,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor ID migration."""
    entry = MockConfigEntry(domain=DOMAIN, data=mock_config)
    entry.add_to_hass(hass)
    model = DEVICE_3080T
    id_phase_range = 1 if model == DEVICE_3080 else 4
    id_name_range = 5 if model == DEVICE_3080 else 7
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
                new_unique_id = (
                    f"{MOCKSN}_{name_list[idx]}"
                    if model == DEVICE_3080
                    else f"{MOCKSN}_{name_list[idx]}_{phase_list[row]}"
                )
                entity_id = ent_reg.async_get_entity_id(
                    DOMAIN, Platform.SENSOR, new_unique_id
                )
                assert entity_id is not None
