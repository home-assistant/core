"""Test Adax climate entity."""

from homeassistant.components.climate.const import ATTR_CURRENT_TEMPERATURE, HVACMode
from homeassistant.components.adax.const import SCAN_INTERVAL
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from tests.common import AsyncMock, async_fire_time_changed
from tests.test_setup import FrozenDateTimeFactory

from . import CLOUD_CONFIG, LOCAL_CONFIG, init_integration
from .conftest import CLOUD_DEVICE_DATA, LOCAL_DEVICE_DATA


async def test_climate_cloud(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_adax_cloud: AsyncMock
) -> None:
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

    mock_adax_cloud.side_effect = Exception()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_climate_local(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_adax_local: AsyncMock
) -> None:
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

    mock_adax_local.side_effect = Exception()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE
