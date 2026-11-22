"""Test the Fast.com sensor."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fastdotcom.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def test_fastdotcom_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_async_fast_com: AsyncMock,
) -> None:
    """Test the Fast.com download sensor state, attributes, and registry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == "100.0"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATA_RATE
    assert (
        state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfDataRate.MEGABITS_PER_SECOND
    )
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    entity_entry = entity_registry.async_get("sensor.fast_com_download")
    assert entity_entry is not None
    assert entity_entry.unique_id == mock_config_entry.entry_id

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert device_entry.configuration_url == "https://www.fast.com"

    mock_config_entry.runtime_data.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.fast_com_download")
    assert state is not None
    assert state.state == STATE_UNKNOWN
