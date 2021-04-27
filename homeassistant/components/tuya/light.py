"""Support for the Tuya lights."""
from datetime import timedelta

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    DOMAIN as SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import color as colorutil

from . import TuyaDevice
from .const import (
    CONF_BRIGHTNESS_RANGE_MODE,
    CONF_MAX_KELVIN,
    CONF_MIN_KELVIN,
    CONF_SUPPORT_COLOR,
    CONF_TUYA_MAX_COLTEMP,
    DEFAULT_TUYA_MAX_COLTEMP,
    DOMAIN,
    SIGNAL_CONFIG_ENTITY,
    TUYA_DATA,
    TUYA_DISCOVERY_NEW,
)

SCAN_INTERVAL = timedelta(seconds=15)

TUYA_BRIGHTNESS_RANGE0 = (1, 255)
TUYA_BRIGHTNESS_RANGE1 = (10, 1000)

BRIGHTNESS_MODES = {
    0: TUYA_BRIGHTNESS_RANGE0,
    1: TUYA_BRIGHTNESS_RANGE1,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tuya sensors dynamically through tuya discovery."""

    platform = config_entry.data[CONF_PLATFORM]

    async def async_discover_sensor(dev_ids):
        """Discover and add a discovered tuya sensor."""
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(
            _setup_entities,
            hass,
            dev_ids,
            platform,
        )
        async_add_entities(entities)

    async_dispatcher_connect(
        hass, TUYA_DISCOVERY_NEW.format(SENSOR_DOMAIN), async_discover_sensor
    )

    devices_ids = hass.data[DOMAIN]["pending"].pop(SENSOR_DOMAIN)
    await async_discover_sensor(devices_ids)


def _setup_entities(hass, dev_ids, platform):
    """Set up Tuya Light device."""
    tuya = hass.data[DOMAIN][TUYA_DATA]
    entities = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        entities.append(TuyaLight(device, platform))
    return entities


class TuyaLight(TuyaDevice, LightEntity):
    """Tuya light device."""

    def __init__(self, tuya, platform):
        """Init Tuya light device."""
        super().__init__(tuya, platform)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())
        self._min_kelvin = tuya.max_color_temp()
        self._max_kelvin = tuya.min_color_temp()

    @callback
    def _process_config(self):
        """Set device config parameter."""
        config = self._get_device_config()
        if not config:
            return

        # support color config
        supp_color = config.get(CONF_SUPPORT_COLOR, False)
        if supp_color:
            self._tuya.force_support_color()
        # brightness range config
        self._tuya.brightness_white_range = BRIGHTNESS_MODES.get(
            config.get(CONF_BRIGHTNESS_RANGE_MODE, 0),
            TUYA_BRIGHTNESS_RANGE0,
        )
        # color set temp range
        min_tuya = self._tuya.max_color_temp()
        min_kelvin = config.get(CONF_MIN_KELVIN, min_tuya)
        max_tuya = self._tuya.min_color_temp()
        max_kelvin = config.get(CONF_MAX_KELVIN, max_tuya)
        self._min_kelvin = min(max(min_kelvin, min_tuya), max_tuya)
        self._max_kelvin = min(max(max_kelvin, self._min_kelvin), max_tuya)
        # color shown temp range
        max_color_temp = max(
            config.get(CONF_TUYA_MAX_COLTEMP, DEFAULT_TUYA_MAX_COLTEMP),
            DEFAULT_TUYA_MAX_COLTEMP,
        )
        self._tuya.color_temp_range = (1000, max_color_temp)

    async def async_added_to_hass(self):
        """Set config parameter when add to hass."""
        await super().async_added_to_hass()
        self._process_config()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONFIG_ENTITY, self._process_config
            )
        )
        return

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self._tuya.brightness() is None:
            return None
        return int(self._tuya.brightness())

    @property
    def hs_color(self):
        """Return the hs_color of the light."""
        return tuple(map(int, self._tuya.hs_color()))

    @property
    def color_temp(self):
        """Return the color_temp of the light."""
        color_temp = int(self._tuya.color_temp())
        if color_temp is None:
            return None
        return colorutil.color_temperature_kelvin_to_mired(color_temp)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._tuya.state()

    @property
    def min_mireds(self):
        """Return color temperature min mireds."""
        return colorutil.color_temperature_kelvin_to_mired(self._max_kelvin)

    @property
    def max_mireds(self):
        """Return color temperature max mireds."""
        return colorutil.color_temperature_kelvin_to_mired(self._min_kelvin)

    def turn_on(self, **kwargs):
        """Turn on or control the light."""
        if (
            ATTR_BRIGHTNESS not in kwargs
            and ATTR_HS_COLOR not in kwargs
            and ATTR_COLOR_TEMP not in kwargs
        ):
            self._tuya.turn_on()
        if ATTR_BRIGHTNESS in kwargs:
            self._tuya.set_brightness(kwargs[ATTR_BRIGHTNESS])
        if ATTR_HS_COLOR in kwargs:
            self._tuya.set_color(kwargs[ATTR_HS_COLOR])
        if ATTR_COLOR_TEMP in kwargs:
            color_temp = colorutil.color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP]
            )
            self._tuya.set_color_temp(color_temp)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._tuya.turn_off()

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = SUPPORT_BRIGHTNESS
        if self._tuya.support_color():
            supports = supports | SUPPORT_COLOR
        if self._tuya.support_color_temp():
            supports = supports | SUPPORT_COLOR_TEMP
        return supports
