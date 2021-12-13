"""Tests for the sensors provided by the Ambee integration."""
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.ambee.const import DEVICE_CLASS_AMBEE_RISK, DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_air_quality(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Ambee Air Quality sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.air_quality_particulate_matter_2_5")
    entry = entity_registry.async_get("sensor.air_quality_particulate_matter_2_5")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_particulate_matter_2_5"
    assert state.state == "3.14"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Particulate Matter < 2.5 μm"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.air_quality_particulate_matter_10")
    entry = entity_registry.async_get("sensor.air_quality_particulate_matter_10")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_particulate_matter_10"
    assert state.state == "5.24"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Particulate Matter < 10 μm"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.air_quality_sulphur_dioxide")
    entry = entity_registry.async_get("sensor.air_quality_sulphur_dioxide")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_sulphur_dioxide"
    assert state.state == "0.031"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Sulphur Dioxide (SO2)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.air_quality_nitrogen_dioxide")
    entry = entity_registry.async_get("sensor.air_quality_nitrogen_dioxide")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_nitrogen_dioxide"
    assert state.state == "0.66"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Nitrogen Dioxide (NO2)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.air_quality_ozone")
    entry = entity_registry.async_get("sensor.air_quality_ozone")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_ozone"
    assert state.state == "17.067"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Ozone"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_BILLION
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.air_quality_carbon_monoxide")
    entry = entity_registry.async_get("sensor.air_quality_carbon_monoxide")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_carbon_monoxide"
    assert state.state == "0.105"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_CO
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Carbon Monoxide (CO)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_MILLION
    )
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.air_quality_air_quality_index")
    entry = entity_registry.async_get("sensor.air_quality_air_quality_index")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_air_quality_air_quality_index"
    assert state.state == "13"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Air Quality Index (AQI)"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_air_quality")}
    assert device_entry.manufacturer == "Ambee"
    assert device_entry.name == "Air Quality"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


async def test_pollen(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Ambee Pollen sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.pollen_grass")
    entry = entity_registry.async_get("sensor.pollen_grass")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_pollen_grass"
    assert state.state == "190"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Grass Pollen"
    assert state.attributes.get(ATTR_ICON) == "mdi:grass"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.pollen_tree")
    entry = entity_registry.async_get("sensor.pollen_tree")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_pollen_tree"
    assert state.state == "127"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Tree Pollen"
    assert state.attributes.get(ATTR_ICON) == "mdi:tree"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.pollen_weed")
    entry = entity_registry.async_get("sensor.pollen_weed")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_pollen_weed"
    assert state.state == "95"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Weed Pollen"
    assert state.attributes.get(ATTR_ICON) == "mdi:sprout"
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes

    state = hass.states.get("sensor.pollen_grass_risk")
    entry = entity_registry.async_get("sensor.pollen_grass_risk")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_pollen_grass_risk"
    assert state.state == "high"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_AMBEE_RISK
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Grass Pollen Risk"
    assert state.attributes.get(ATTR_ICON) == "mdi:grass"
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    state = hass.states.get("sensor.pollen_tree_risk")
    entry = entity_registry.async_get("sensor.pollen_tree_risk")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_pollen_tree_risk"
    assert state.state == "moderate"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_AMBEE_RISK
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Tree Pollen Risk"
    assert state.attributes.get(ATTR_ICON) == "mdi:tree"
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    state = hass.states.get("sensor.pollen_weed_risk")
    entry = entity_registry.async_get("sensor.pollen_weed_risk")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_pollen_weed_risk"
    assert state.state == "high"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_AMBEE_RISK
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Weed Pollen Risk"
    assert state.attributes.get(ATTR_ICON) == "mdi:sprout"
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}_pollen")}
    assert device_entry.manufacturer == "Ambee"
    assert device_entry.name == "Pollen"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert not device_entry.model
    assert not device_entry.sw_version


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.pollen_grass_poaceae",
        "sensor.pollen_tree_alder",
        "sensor.pollen_tree_birch",
        "sensor.pollen_tree_cypress",
        "sensor.pollen_tree_elm",
        "sensor.pollen_tree_hazel",
        "sensor.pollen_tree_oak",
        "sensor.pollen_tree_pine",
        "sensor.pollen_tree_plane",
        "sensor.pollen_tree_poplar",
        "sensor.pollen_weed_chenopod",
        "sensor.pollen_weed_mugwort",
        "sensor.pollen_weed_nettle",
        "sensor.pollen_weed_ragweed",
    ),
)
async def test_pollen_disabled_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str
) -> None:
    """Test the Ambee Pollen sensors that are disabled by default."""
    entity_registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state is None

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == er.DISABLED_INTEGRATION


@pytest.mark.parametrize(
    "key,icon,name,value",
    [
        ("grass_poaceae", "mdi:grass", "Poaceae Grass Pollen", "190"),
        ("tree_alder", "mdi:tree", "Alder Tree Pollen", "0"),
        ("tree_birch", "mdi:tree", "Birch Tree Pollen", "35"),
        ("tree_cypress", "mdi:tree", "Cypress Tree Pollen", "0"),
        ("tree_elm", "mdi:tree", "Elm Tree Pollen", "0"),
        ("tree_hazel", "mdi:tree", "Hazel Tree Pollen", "0"),
        ("tree_oak", "mdi:tree", "Oak Tree Pollen", "55"),
        ("tree_pine", "mdi:tree", "Pine Tree Pollen", "30"),
        ("tree_plane", "mdi:tree", "Plane Tree Pollen", "5"),
        ("tree_poplar", "mdi:tree", "Poplar Tree Pollen", "0"),
        ("weed_chenopod", "mdi:sprout", "Chenopod Weed Pollen", "0"),
        ("weed_mugwort", "mdi:sprout", "Mugwort Weed Pollen", "1"),
        ("weed_nettle", "mdi:sprout", "Nettle Weed Pollen", "88"),
        ("weed_ragweed", "mdi:sprout", "Ragweed Weed Pollen", "3"),
    ],
)
async def test_pollen_enable_disable_by_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ambee: AsyncMock,
    key: str,
    icon: str,
    name: str,
    value: str,
) -> None:
    """Test the Ambee Pollen sensors that are disabled by default."""
    entry_id = mock_config_entry.entry_id
    entity_id = f"{SENSOR_DOMAIN}.pollen_{key}"
    entity_registry = er.async_get(hass)

    # Pre-create registry entry for disabled by default sensor
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{entry_id}_pollen_{key}",
        suggested_object_id=f"pollen_{key}",
        disabled_by=None,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_pollen_{key}"
    assert state.state == value
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == name
    assert state.attributes.get(ATTR_ICON) == icon
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == CONCENTRATION_PARTS_PER_CUBIC_METER
    )
    assert ATTR_DEVICE_CLASS not in state.attributes
