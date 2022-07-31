"""Tests for the sensor provided by the CPU Speed integration."""

from unittest.mock import MagicMock

from homeassistant.components.cpuspeed.const import DOMAIN
from homeassistant.components.cpuspeed.sensor import ATTR_ARCH, ATTR_BRAND, ATTR_HZ
from homeassistant.components.homeassistant import (
    DOMAIN as HOME_ASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_sensor(
    hass: HomeAssistant,
    mock_cpuinfo: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the CPU Speed sensor."""
    await async_setup_component(hass, "homeassistant", {})
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entry = entity_registry.async_get("sensor.cpu_speed")
    assert entry
    assert entry.unique_id == entry.config_entry_id
    assert entry.entity_category is None

    state = hass.states.get("sensor.cpu_speed")
    assert state
    assert state.state == "3.2"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "CPU Speed"
    assert state.attributes.get(ATTR_ICON) == "mdi:pulse"
    assert ATTR_DEVICE_CLASS not in state.attributes

    assert state.attributes.get(ATTR_ARCH) == "aargh"
    assert state.attributes.get(ATTR_BRAND) == "Intel Ryzen 7"
    assert state.attributes.get(ATTR_HZ) == 3.6

    mock_cpuinfo.return_value = {}
    await hass.services.async_call(
        HOME_ASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.cpu_speed"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.cpu_speed")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ARCH) == "aargh"
    assert state.attributes.get(ATTR_BRAND) == "Intel Ryzen 7"
    assert state.attributes.get(ATTR_HZ) == 3.6

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, entry.config_entry_id)}
    assert device_entry.name == "CPU Speed"


async def test_sensor_partial_info(
    hass: HomeAssistant,
    mock_cpuinfo: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the CPU Speed sensor missing info."""
    mock_config_entry.add_to_hass(hass)

    # Pop some info from the mocked CPUSpeed
    mock_cpuinfo.return_value.pop("brand_raw")
    mock_cpuinfo.return_value.pop("arch_string_raw")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.cpu_speed")
    assert state
    assert state.state == "3.2"
    assert state.attributes.get(ATTR_ARCH) is None
    assert state.attributes.get(ATTR_BRAND) is None
