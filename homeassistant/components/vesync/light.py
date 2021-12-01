"""Support for VeSync bulbs and wall dimmers."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncDevice
from .const import DEV_TYPE_TO_HA, DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_LIGHTS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights."""

    async def async_discover(devices):
        """Add new devices to platform."""
        _async_setup_entities(devices, async_add_entities)

    disp = async_dispatcher_connect(
        hass, VS_DISCOVERY.format(VS_LIGHTS), async_discover
    )
    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

    _async_setup_entities(hass.data[DOMAIN][VS_LIGHTS], async_add_entities)


@callback
def _async_setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) in ("walldimmer", "bulb-dimmable"):
            entities.append(VeSyncDimmableLightHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) in ("bulb-tunable-white",):
            entities.append(VeSyncTunableWhiteLightHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "humidifier":
            entities.append(VeSyncHumidifierNightLightHA(dev))
        else:
            _LOGGER.debug(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


def _vesync_brightness_to_ha(vesync_brightness):
    try:
        # check for validity of brightness value received
        brightness_value = int(vesync_brightness)
    except ValueError:
        # deal if any unexpected/non numeric value
        _LOGGER.debug(
            "VeSync - received unexpected 'brightness' value from pyvesync api: %s",
            vesync_brightness,
        )
        return 0
    # convert percent brightness to ha expected range
    return round((max(1, brightness_value) / 100) * 255)


def _ha_brightness_to_vesync(ha_brightness):
    # get brightness from HA data
    brightness = int(ha_brightness)
    # ensure value between 1-255
    brightness = max(1, min(brightness, 255))
    # convert to percent that vesync api expects
    brightness = round((brightness / 255) * 100)
    # ensure value between 1-100
    brightness = max(1, min(brightness, 100))

    return brightness


class VeSyncBaseLight(VeSyncDevice, LightEntity):
    """Base class for VeSync Light Devices Representations."""

    @property
    def brightness(self):
        """Get light brightness."""
        # get value from pyvesync library api,
        return _vesync_brightness_to_ha(self.device.brightness)

    def turn_on(self, **kwargs):
        """Turn the device on."""
        attribute_adjustment_only = False
        # set white temperature
        if self.color_mode in (COLOR_MODE_COLOR_TEMP,) and ATTR_COLOR_TEMP in kwargs:
            # get white temperature from HA data
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            # ensure value between min-max supported Mireds
            color_temp = max(self.min_mireds, min(color_temp, self.max_mireds))
            # convert Mireds to Percent value that api expects
            color_temp = round(
                ((color_temp - self.min_mireds) / (self.max_mireds - self.min_mireds))
                * 100
            )
            # flip cold/warm to what pyvesync api expects
            color_temp = 100 - color_temp
            # ensure value between 0-100
            color_temp = max(0, min(color_temp, 100))
            # call pyvesync library api method to set color_temp
            self.device.set_color_temp(color_temp)
            # flag attribute_adjustment_only, so it doesn't turn_on the device redundantly
            attribute_adjustment_only = True
        # set brightness level
        if (
            self.color_mode in (COLOR_MODE_BRIGHTNESS, COLOR_MODE_COLOR_TEMP)
            and ATTR_BRIGHTNESS in kwargs
        ):
            # get brightness from HA data
            brightness = _ha_brightness_to_vesync(kwargs[ATTR_BRIGHTNESS])
            self.device.set_brightness(brightness)
            # flag attribute_adjustment_only, so it doesn't turn_on the device redundantly
            attribute_adjustment_only = True
        # check flag if should skip sending the turn_on command
        if attribute_adjustment_only:
            return
        # send turn_on command to pyvesync api
        self.device.turn_on()


class VeSyncDimmableLightHA(VeSyncBaseLight, LightEntity):
    """Representation of a VeSync dimmable light device."""

    @property
    def color_mode(self):
        """Set color mode for this entity."""
        return COLOR_MODE_BRIGHTNESS

    @property
    def supported_color_modes(self):
        """Flag supported color_modes (in an array format)."""
        return [COLOR_MODE_BRIGHTNESS]


class VeSyncTunableWhiteLightHA(VeSyncBaseLight, LightEntity):
    """Representation of a VeSync Tunable White Light device."""

    @property
    def color_temp(self):
        """Get device white temperature."""
        # get value from pyvesync library api,
        result = self.device.color_temp_pct
        try:
            # check for validity of brightness value received
            color_temp_value = int(result)
        except ValueError:
            # deal if any unexpected/non numeric value
            _LOGGER.debug(
                "VeSync - received unexpected 'color_temp_pct' value from pyvesync api: %s",
                result,
            )
            return 0
        # flip cold/warm
        color_temp_value = 100 - color_temp_value
        # ensure value between 0-100
        color_temp_value = max(0, min(color_temp_value, 100))
        # convert percent value to Mireds
        color_temp_value = round(
            self.min_mireds
            + ((self.max_mireds - self.min_mireds) / 100 * color_temp_value)
        )
        # ensure value between minimum and maximum Mireds
        return max(self.min_mireds, min(color_temp_value, self.max_mireds))

    @property
    def min_mireds(self):
        """Set device coldest white temperature."""
        return 154  # 154 Mireds ( 1,000,000 divided by 6500 Kelvin = 154 Mireds)

    @property
    def max_mireds(self):
        """Set device warmest white temperature."""
        return 370  # 370 Mireds  ( 1,000,000 divided by 2700 Kelvin = 370 Mireds)

    @property
    def color_mode(self):
        """Set color mode for this entity."""
        return COLOR_MODE_COLOR_TEMP

    @property
    def supported_color_modes(self):
        """Flag supported color_modes (in an array format)."""
        return [COLOR_MODE_COLOR_TEMP]


class VeSyncHumidifierNightLightHA(VeSyncDimmableLightHA):
    """Representation of the night light on a VeSync humidifier."""

    def __init__(self, humidifier):
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier)
        self.smarthumidifier = humidifier

    @property
    def unique_id(self):
        """Return the ID of this device."""
        return f"{super().unique_id}-night-light"

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} night light"

    @property
    def brightness(self):
        """Get night light brightness."""
        # get value from pyvesync library api,
        return _vesync_brightness_to_ha(
            self.smarthumidifier.details["night_light_brightness"]
        )

    @property
    def is_on(self):
        """Return True if night light is on."""
        return self.smarthumidifier.details["night_light_brightness"] > 0

    @property
    def entity_category(self):
        """Return the configuration entity category."""
        return EntityCategory.CONFIG

    def turn_on(self, **kwargs):
        """Turn the night light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = _ha_brightness_to_vesync(kwargs[ATTR_BRIGHTNESS])
            self.smarthumidifier.set_night_light_brightness(brightness)
        else:
            self.smarthumidifier.set_night_light_brightness(100)

    def turn_off(self, **kwargs):
        """Turn the night light off."""
        self.smarthumidifier.set_night_light_brightness(0)
