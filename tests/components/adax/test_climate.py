"""Test Adax climate entity."""

from homeassistant.components.climate.const import ATTR_CURRENT_TEMPERATURE, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import CLOUD_CONFIG, LOCAL_CONFIG, init_integration
from .conftest import CLOUD_DEVICE_DATA, LOCAL_DEVICE_DATA


async def test_climate_cloud(hass: HomeAssistant, mock_adax_cloud) -> None:
    """Test states of the (cloud) Climate entity."""
    await init_integration(
        hass,
        entry_data=CLOUD_CONFIG,
    )
    mock_adax_cloud.assert_called_once()

    assert len(hass.states.async_entity_ids(Platform.CLIMATE)) == 1
    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    state = hass.states.get(entity_id)

    assert state
    assert state.state == HVACMode.HEAT
    assert (
        state.attributes[ATTR_TEMPERATURE] == CLOUD_DEVICE_DATA[0]["targetTemperature"]
    )
    assert (
        state.attributes[ATTR_CURRENT_TEMPERATURE]
        == CLOUD_DEVICE_DATA[0]["temperature"]
    )


async def test_climate_local(hass: HomeAssistant, mock_adax_local) -> None:
    """Test states of the (local) Climate entity."""
    await init_integration(
        hass,
        entry_data=LOCAL_CONFIG,
    )
    mock_adax_local.assert_called_once()

    assert len(hass.states.async_entity_ids(Platform.CLIMATE)) == 1
    entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

    await async_update_entity(hass, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == HVACMode.HEAT
    assert (
        state.attributes[ATTR_TEMPERATURE] == (LOCAL_DEVICE_DATA["target_temperature"])
    )
    assert (
        state.attributes[ATTR_CURRENT_TEMPERATURE]
        == (LOCAL_DEVICE_DATA["current_temperature"])
    )
