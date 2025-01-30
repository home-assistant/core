from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.const import STATE_ON, STATE_OFF, CONF_BRIGHTNESS
from .const import API_URL
import aiohttp
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the light platform."""
    access_token = config_entry.data.get("access_token")
    if access_token:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{API_URL}/home_assistant?access_token={access_token}') as response:
                    if response.status == 200:
                        data = await response.json()
                        entities = []
                        
                        for item in data.get("boards", []):
                            endpoint_id = item.get('endpointId', '')
                            if 'dim' in endpoint_id:
                                entities.append(RedgtechLight(item, access_token))
                        
                        async_add_entities(entities)
                    else:
                        _LOGGER.error("Error fetching data from API: %s", response.status)
        except aiohttp.ClientError as e:
            _LOGGER.error("Error connecting to API: %s", e)
    else:
        _LOGGER.error("No access token available")


class RedgtechLight(LightEntity):
    """Representation of a dimmable light."""

    def __init__(self, data, token):
        self._state = STATE_ON if data.get("value", False) else STATE_OFF
        self._brightness = self._convert_brightness(data.get("bright", 0))
        self._previous_brightness = self._brightness
        self._name = data.get("friendlyName")
        self._endpoint_id = data.get("endpointId")
        self._description = data.get("description")
        self._manufacturer = data.get("manufacturerName")
        self._token = token
        self._supported_color_modes = {ColorMode.BRIGHTNESS}
        self._color_mode = ColorMode.BRIGHTNESS

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._state == STATE_ON

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def supported_color_modes(self):
        """Return supported color modes."""
        return self._supported_color_modes

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return self._color_mode

    async def async_turn_on(self, **kwargs):
        """Turn the light on with optional brightness."""
        brightness = kwargs.get(CONF_BRIGHTNESS, self._previous_brightness)
        await self._set_state(STATE_ON, brightness)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._previous_brightness = self._brightness
        await self._set_state(STATE_OFF)

    async def _set_state(self, state, brightness=None):
        """Send the state and brightness to the API to update the light."""
        id_part, after_id = self._endpoint_id.split("-", 1)
        number_channel = after_id[-1]
        type_channel = ''.join(char for char in after_id if char.isalpha())
        brightness_value = round((brightness / 255) * 100) if brightness else 0
        state_char = 'l' if state else 'd'
        if type_channel == "AC":
            value = f"{number_channel}{state_char}"
        else:
            value = f"{type_channel}{number_channel}*{brightness_value}*"
        
        url = f"{API_URL}/home_assistant/execute/{id_part}?cod=?{value}"
        headers = {"Authorization": f"{self._token}"}
        payload = {"state": state}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    self._state = state
                    if state == STATE_ON:
                        self._brightness = brightness or 255
                    else:
                        self._brightness = 0
                    self.async_write_ha_state()
                else:
                    _LOGGER.error("Failed to set state for %s, status code: %s", self._name, response.status)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "endpoint_id": self._endpoint_id,
            "description": self._description,
            "manufacturer": self._manufacturer,
        }

    def _convert_brightness(self, bright_value):
        """Convert brightness value from 0-100 to 0-255."""
        try:
            return int((int(bright_value) / 100) * 255)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid brightness value: %s", bright_value)
            return 0