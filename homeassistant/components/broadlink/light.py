"""Support for Broadlink lights."""
from abc import ABC, abstractmethod
from functools import partial
import logging

from broadlink.exceptions import BroadlinkException
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    FLASH_LONG,
    FLASH_SHORT,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    COLOR_MODE_HS,
    LightEntity,
)
from homeassistant.const import (
    ATTR_MODE,
    ATTR_ENTITY_ID,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_HOSTS,
    CONF_MAC,
    CONF_NAME,
    CONF_SWITCHES,
    CONF_LIGHTS,
    CONF_TIMEOUT,
    CONF_TYPE,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import ToggleEntity

from .const import DOMAIN, LIGHT_DOMAIN
from .helpers import data_packet, import_device, mac_address

_LOGGER = logging.getLogger(__name__)

CONF_SLOTS = "slots"

# SWITCH_SCHEMA = vol.Schema(
#     {
#         vol.Required(CONF_NAME): cv.string,
#         vol.Optional(CONF_COMMAND_OFF): data_packet,
#         vol.Optional(CONF_COMMAND_ON): data_packet,
#     }
# )

# OLD_SWITCH_SCHEMA = vol.Schema(
#     {
#         vol.Optional(CONF_COMMAND_OFF): data_packet,
#         vol.Optional(CONF_COMMAND_ON): data_packet,
#         vol.Optional(CONF_FRIENDLY_NAME): cv.string,
#     }
# )

# PLATFORM_SCHEMA = vol.All(
#     cv.deprecated(CONF_HOST),
#     cv.deprecated(CONF_SLOTS),
#     cv.deprecated(CONF_TIMEOUT),
#     cv.deprecated(CONF_TYPE),
#     PLATFORM_SCHEMA.extend(
#         {
#             vol.Required(CONF_MAC): mac_address,
#             vol.Optional(CONF_HOST): cv.string,
#             vol.Optional(CONF_SWITCHES, default=[]): vol.Any(
#                 cv.schema_with_slug_keys(OLD_SWITCH_SCHEMA),
#                 vol.All(cv.ensure_list, [SWITCH_SCHEMA]),
#             ),
#         }
#     ),
# )

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOSTS): vol.All(cv.ensure_list, [cv.string])}
)

def color_rgb_to_int(red: int, green: int, blue: int) -> int:
    """Return a RGB color as an integer."""
    return red * 256 * 256 + green * 256 + blue


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the device and set up custom lights.

    This is for backward compatibility.
    Do not use this method.
    """
    mac_addr = config[CONF_MAC]
    host = config.get(CONF_HOST)
    lights = config.get(CONF_LIGHTS)

    if not isinstance(lights, list):
        lights = [
            {CONF_NAME: light.pop(CONF_FRIENDLY_NAME, name), **light}
            for name, light in lights.items()
        ]

        _LOGGER.warning(
            "Your configuration for the light platform is deprecated. "
            "Please refer to the Broadlink documentation to catch up"
        )

    if lights:
        platform_data = hass.data[DOMAIN].platforms.setdefault(LIGHT_DOMAIN, {})
        platform_data.setdefault(mac_addr, []).extend(lights)

    else:
        _LOGGER.warning(
            "The switch platform is deprecated, except for custom IR/RF "
            "switches. Please refer to the Broadlink documentation to "
            "catch up"
        )

    if host:
        import_device(hass, host)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink light."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    # if device.api.type == "LB1":
    #     platform_data = hass.data[DOMAIN].platforms.get(SWITCH_DOMAIN, {})
    #     user_defined_lights = platform_data.get(device.api.mac, {})
    #     switches = [
    #         BroadlinkRMSwitch(device, config) for config in user_defined_switches
    #     ]

    if device.api.type == "LB1":
        lights = [BroadlinkLB1Light(device)]

    async_add_entities(lights)


class BroadlinkLight(LightEntity):#, ToggleEntity, ABC):
    """Representation of a Broadlink light."""

    def __init__(self, device):
        """Initialize the light."""
        self._device = device
        self._red = 255
        self._blue = 255
        self._green = 255
        self._brightness = 255
        self._colormode = 1
        self._hs_color = [0, 100]
        self._colortemp = 2700
        self._coordinator = device.update_manager.coordinator
        self._state = None

    @property
    def name(self):
        """Return the name of the light."""
        return f"{self._device.name} Light"

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the switch."""
        return True

    @property
    def available(self):
        """Return True if the switch is available."""
        return self._device.update_manager.available

    @property
    def is_on(self):
        """Return True if the switch is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs_color

    @property
    def should_poll(self):
        """Return True if the switch has to be polled for state."""
        return False

    @property
    def device_class(self):
        """Return device class."""
        return "light"

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    @property
    def color_mode(self):
        return COLOR_MODE_HS

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "manufacturer": self._device.api.manufacturer,
            "model": self._device.api.model,
            "name": self._device.name,
            "sw_version": self._device.fw_version,
        }

    @callback
    def update_data(self):
        """Update data."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the light is added to hass."""
        if self._state is None:
            data = await self._device.async_request(self._device.api.get_state)
            _LOGGER.info(f"add to hass with data {data}")
            self._state = data['pwr']
            self._brightness = round(data['brightness']*2.55)
            self._hs_color = [data['hue'], data['saturation']]
        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the switch."""
        await self._coordinator.async_request_refresh()

    async def async_toggle(self, **kwargs):
        _LOGGER.info(f"light async toggle with state {self._state}")
        if await self._async_send_packet("pwr", 0 if self._state else 1):
            self._state = not self._state
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        hs_color = kwargs.get(ATTR_HS_COLOR, self._hs_color)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        data = {
            "hue": hs_color[0], 
            "saturation": hs_color[1], 
            "bulb_colormode": 1 if hs_color[1] == 0 else 0,
            "brightness": round(brightness/2.55),
            "pwr": 1
        }

        _LOGGER.info(f"light async turn on with hs_color {hs_color} and brightness {brightness} and state {self._state}")

        if await self._async_send_packet(data):
            self._hs_color = hs_color
            self._brightness = brightness
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        _LOGGER.info(f"light async turn off with state {self._state}")
        if await self._async_send_packet("pwr",0):
            self._state = False
            self.async_write_ha_state()

    @abstractmethod
    async def _async_send_packet(self, packet):
        """Send a packet to the device."""


class BroadlinkLB1Light(BroadlinkLight):
    """Representation of a Broadlink RM switch."""

    def __init__(self, device):
        """Initialize the switch."""
        super().__init__(device)
        self._name = f"{device.name} Light"

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    async def _async_send_packet(self, request):
        """Send a packet to the device."""
        _LOGGER.info(f"async send packet with packet {request}")
        if request is None:
            return True

        try:
            await self._device.async_request(self._device.api.set_state, **request)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True

