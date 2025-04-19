"""Test Adax climate entity."""

from homeassistant.components.adax.climate import AdaxDevice
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import CLOUD_CONFIG, init_integration
from .conftest import CLOUD_DEVICE_DATA

from tests.common import AsyncMock, patch


async def test_climate_set_temperature_to_zero(
    hass: HomeAssistant, mock_adax_cloud: AsyncMock
) -> None:
    """Test states of the (cloud) Climate entity."""
    with patch("adax.Adax.update") as mock_adax_update:
        mock_adax_update.return_value = None

        with patch("adax.Adax.set_room_target_temperature") as mock_adax_set_temp:
            mock_adax_set_temp.return_value = None
            await init_integration(
                hass,
                entry_data=CLOUD_CONFIG,
            )
            assert len(hass.states.async_entity_ids(Platform.CLIMATE)) == 1
            entity_id = hass.states.async_entity_ids(Platform.CLIMATE)[0]

            device: AdaxDevice = hass.data["domain_entities"][Platform.CLIMATE][
                entity_id
            ]

            # Assert state before temp change
            state = hass.states.get(entity_id)
            assert state
            assert state.state == HVACMode.HEAT
            assert (
                state.attributes[ATTR_TEMPERATURE]
                == CLOUD_DEVICE_DATA[0]["targetTemperature"]
            )

            # Set temperature to 0, which should turn-off the device
            await device.async_set_temperature(temperature=0)
            mock_adax_set_temp.assert_called_once_with(
                device._device_id, device._attr_min_temp, False
            )
            CLOUD_DEVICE_DATA[0]["heatingEnabled"] = False
            CLOUD_DEVICE_DATA[0]["targetTemperature"] = 0
            mock_adax_cloud.return_value = CLOUD_DEVICE_DATA

            await async_update_entity(hass, entity_id)

            # Assert state after temp change
            state = hass.states.get(entity_id)
            assert state
            assert state.state == HVACMode.OFF
            assert state.attributes[ATTR_TEMPERATURE] == 0
