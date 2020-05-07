"""Support for LimitlessLED bulbs directly via SPI-connected LT8900."""

import logging
import time

import gpiozero
import limitlessled_rf
import lt8900_spi
import voluptuous

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    Light,
)
import homeassistant.helpers.config_validation as config_validation
from homeassistant.util.color import (
    color_hs_to_RGB,
    color_RGB_to_hs,
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_REMOTE_TYPE = "rgbw"
DEFAULT_REMOTE_INCLUDE_ALL = "False"
DEFAULT_REMOTE_FORMAT = "limitlessled_remote{}{}"
DEFAULT_ZONE_FORMAT = "_zone{}"
CONF_RADIO_SECTION = "radio"
CONF_RADIO_GPIO_PIN = "gpio_pin"
CONF_RADIO_SPI_BUS = "spi_bus"
CONF_RADIO_SPI_DEV = "spi_device"
CONF_RADIO_TYPE = "type"
CONF_REMOTE_FORMAT = "remote_format"
CONF_ZONE_FORMAT = "zone_format"
CONF_REMOTES_SECTION = "remotes"
CONF_REMOTE_START = "start"
CONF_REMOTE_TYPE = "type"
CONF_REMOTE_COUNT = "count"
CONF_REMOTE_ZONES = "zones"
CONF_REMOTE_RETRIES = "retries"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        voluptuous.Optional(CONF_RADIO_SECTION): voluptuous.All(
            {
                voluptuous.Optional(
                    CONF_RADIO_GPIO_PIN
                ): config_validation.positive_int,
                voluptuous.Optional(CONF_RADIO_SPI_BUS): config_validation.positive_int,
                voluptuous.Optional(CONF_RADIO_SPI_DEV): config_validation.positive_int,
                voluptuous.Optional(CONF_RADIO_TYPE): config_validation.string,
            }
        ),
        voluptuous.Optional(CONF_REMOTE_RETRIES): config_validation.positive_int,
        voluptuous.Optional(CONF_REMOTE_FORMAT): config_validation.match_all,
        voluptuous.Optional(CONF_ZONE_FORMAT): config_validation.match_all,
        voluptuous.Optional(CONF_REMOTES_SECTION): voluptuous.All(
            config_validation.ensure_list,
            [
                {
                    voluptuous.Optional(
                        CONF_REMOTE_START
                    ): config_validation.positive_int,
                    voluptuous.Optional(CONF_REMOTE_TYPE): config_validation.string,
                    voluptuous.Optional(
                        CONF_REMOTE_COUNT
                    ): config_validation.positive_int,
                    voluptuous.Optional(
                        CONF_REMOTE_ZONES
                    ): config_validation.ensure_list,
                    voluptuous.Optional(
                        CONF_REMOTE_RETRIES
                    ): config_validation.positive_int,
                    voluptuous.Optional(
                        CONF_REMOTE_FORMAT
                    ): config_validation.match_all,
                    voluptuous.Optional(CONF_ZONE_FORMAT): config_validation.match_all,
                }
            ],
        ),
    }
)


def _debug_log(source, message):
    _LOGGER.debug("[" + source + "] " + message)


def _info_log(source, message):
    _LOGGER.info("[" + source + "] " + message)


def _error_log(source, message):
    _LOGGER.error("[" + source + "] " + message)


def _init_radio_lt8900(radio_config):
    gpio_pin = radio_config.get(CONF_RADIO_GPIO_PIN)
    spi_bus = radio_config.get(CONF_RADIO_SPI_BUS, 0)
    spi_dev = radio_config.get(CONF_RADIO_SPI_DEV, 0)

    reset_module_via_gpio = None
    if gpio_pin is not None:
        # Need to keep this attached to drive the line high -- if the object disappears then
        # the GPIO port gets reconfigured as an input port
        # Note: broadcom pin numbers are used
        gpio_pin = int(gpio_pin)

        def reset_module_via_gpio_func(gpio_pin):
            global reset_gpio
            reset_gpio = None
            reset_gpio = gpiozero.LED(gpio_pin)
            reset_gpio.off()
            time.sleep(0.1)
            reset_gpio.on()
            time.sleep(0.1)

        reset_module_via_gpio = (lambda: reset_module_via_gpio_func(gpio_pin))

    # LT8900 compatible radio
    radio = lt8900_spi.Radio(
        spi_bus,
        spi_dev,
        config={
            "reset_command": reset_module_via_gpio,
            "use_software_tx_queue": True,
            "__DISABLED__debug_log_command": (
                lambda message: _debug_log("LT8900", message)
            ),
            "info_log_command": (lambda message: _info_log("LT8900", message)),
            "error_log_command": (lambda message: _error_log("LT8900", message)),
        },
    )

    if not radio.initialize():
        return None

    return radio


def _str_to_bool(value):
    return value.lower() in ["true", "t", "y", "yes", "1"]


def _rgb_list_to_int(rgb_list):
    value = 0
    value |= rgb_list[0] << 16
    value |= rgb_list[1] << 8
    value |= rgb_list[2]
    return value


def _format_entity_name(remote_id, zone_id, remote_format, zone_format):
    if zone_id == 0:
        zone_str = ""
    else:
        try:
            zone_str = zone_format.format(zone_id)
        except Exception as failure:
            zone_str = DEFAULT_ZONE_FORMAT.format(zone_id)
            failure = failure.copy()

    try:
        name = remote_format.format(remote_id, zone_str)
    except Exception as failure:
        name = DEFAULT_REMOTE_FORMAT.format(remote_id, zone_str)
        failure = failure.copy()

    return name


def _find_bulb_by_event(remotes_zones, event):
    entity_id = event.data.get("entity_id")
    if entity_id is None:
        return None
    entity_id = entity_id.split(".")
    entity_type = entity_id[0]
    if entity_type != "light":
        return None

    remote_name = entity_id[1]
    for remote in remotes_zones:
        if remote.name == remote_name:
            return remote
    return None


def _pair_bulb(remotes_zones, event):
    remote = _find_bulb_by_event(remotes_zones, event)
    if remote is not None:
        remote.handle_pair()
    return None


def _unpair_bulb(remotes_zones, event):
    remote = _find_bulb_by_event(remotes_zones, event)
    if remote is not None:
        remote.handle_unpair()
    return None


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Configure Home Assistant to be aware of all entities specified in the configuration file."""
    remotes_zones = []

    # Initialize the radio
    radio_config = config.get(CONF_RADIO_SECTION, {})
    radio_type = radio_config.get("type", "lt8900")

    # Default parameters for all remotes
    default_remote_format = config.get(CONF_REMOTE_FORMAT, DEFAULT_REMOTE_FORMAT)
    default_zone_format = config.get(CONF_ZONE_FORMAT, DEFAULT_ZONE_FORMAT)
    default_remote_retries = config.get(CONF_REMOTE_RETRIES, 0)

    if radio_type == "lt8900":
        radio = _init_radio_lt8900(radio_config)
    else:
        raise f"Unsupported radio type {radio_type}"

    # For each remote, create backing objects
    for remote_config in config.get(CONF_REMOTES_SECTION, []):
        # Remotes are identified by a 16-bit integer, allow the
        # user to create many sequential remotes of the same type
        # in a single go;  Each remote can have multiple zones
        remote_type = remote_config.get(CONF_REMOTE_TYPE, DEFAULT_REMOTE_TYPE)
        remote_id_start = remote_config.get(CONF_REMOTE_START, 1)
        remote_id_count = remote_config.get(CONF_REMOTE_COUNT, 1)

        # Compute naming format strings for this remote, which may
        # either be the default or a remote-specific one
        remote_format = remote_config.get(CONF_REMOTE_FORMAT, default_remote_format)
        zone_format = remote_config.get(CONF_ZONE_FORMAT, default_zone_format)

        # Allow some remotes to have higher retries
        zone_retries = remote_config.get(CONF_REMOTE_RETRIES, default_remote_retries)

        for remote_id_index in range(remote_id_count):
            remote_id = remote_id_start + remote_id_index
            remote_global_name = _format_entity_name(
                remote_id, 0, remote_format, zone_format
            )

            # Compute configuration for this remote
            remote_config_parameters = {
                "__DISABLED__debug_log_command": (
                    lambda message: _debug_log("REMOTE " + remote_global_name, message)
                ),
                "radio_queue": remote_global_name,
            }
            if zone_retries != 0:
                remote_config_parameters["retries"] = zone_retries

            remote = limitlessled_rf.Remote(
                radio, remote_type, remote_id, config=remote_config_parameters
            )

            # Default to all the zones in the remote, plus the whole remote
            remote_zone_ids = [0] + remote.get_zone_ids()

            # Allow the user to specify which zones they want
            remote_zone_ids = remote_config.get(CONF_REMOTE_ZONES, remote_zone_ids)

            # For each zone (that is, not including the whole remote) make those available
            # to Home Assistant
            remote_zones = []
            for zone_id in remote_zone_ids:
                if zone_id == 0:
                    continue

                remote_zone_name = _format_entity_name(
                    remote_id, zone_id, remote_format, zone_format
                )

                remote_zone = LimitlessLED_RF_HASS(remote_zone_name, remote, zone_id)
                remotes_zones.append(remote_zone)
                remote_zones.append(remote_zone)

            # If the entire remote is included, let it know about the other zone objects
            if 0 in remote_zone_ids:
                remotes_zones.append(
                    LimitlessLED_RF_HASS(remote_global_name, remote, None, remote_zones)
                )

    # Register an event handler to pair or unpair a bulb
    hass.bus.listen(
        "limitlessled_rf_pair", (lambda event: _pair_bulb(remotes_zones, event))
    )
    hass.bus.listen(
        "limitlessled_rf_unpair", (lambda event: _unpair_bulb(remotes_zones, event))
    )

    add_entities(remotes_zones)


class LimitlessLED_RF_HASS(Light):
    """HomeAssistant Representation of a LimitessLED (remote, zone)."""

    def __init__(self, name, remote, zone, child_zones=[]):
        """Create a new LimitlessLED (remote, zone) or remote tuple for Home Assistant to interact with."""
        self._name = name
        self._remote = remote
        self._zone = zone
        self._child_zones = child_zones

        # Assume the initial bulb state
        self._state_on = True
        self._brightness = 128
        self._color = 0x800000

        # XXX: Determine if this is cool/warm rgbw bulb ?
        self._temperature = 5000

        # Enforce our world view ?
        if False and zone is None:
            if self._state_on:
                self._remote.on(self._zone)
                self._remote.set_color(self._color, self._zone)
                self._remote.set_temperature(self._temperature, self._zone)
                self._remote.set_brightness(self._brightness, self._zone)
            else:
                self._remote.off(self._zone)

        return None

    def _debug_log(self, message):
        _debug_log("HASS", f"{self._name}: {message}")
        return None

    def _info_log(self, message):
        _info_log("HASS", f"{self._name}: {message}")
        return None

    def handle_pair(self):
        """Handle bulb-type specific pairing into this (remote, zone), used by event handler."""
        if self._zone is None:
            return None
        self._debug_log("Asked to pair")
        self._remote.pair(self._zone)
        return None

    def handle_unpair(self):
        """Handle bulb-type specific unpairing, used by event handler."""
        if self._zone is None:
            return None
        self._debug_log("Asked to unpair")
        self._remote.unpair(self._zone)
        return None

    @property
    def name(self):
        """Return the unique name of this (remote, zone) object."""
        return self._name

    @property
    def supported_features(self):
        """Return which features this bulb-type supports."""
        if self._remote.get_type() == "rgbw":
            features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR
        elif self._remote.get_type() == "cct":
            features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

        return features

    @property
    def is_on(self):
        """Return whether the bulb is recorded as being on or not."""
        return self._state_on

    def propagate_copy(self, other, attrs_to_copy):
        """Copy changes to zones on a remote.

        When the whole remote is acted upon, filter the change
        applied to every bulb that is paired with any zone on that
        remote.
        """
        self._debug_log(
            "Copying state ({}) from parent (parent is {})".format(
                attrs_to_copy, other.name
            )
        )
        if "state_on" in attrs_to_copy:
            self._state_on = other.is_on
        if "brightness" in attrs_to_copy:
            self._brightness = other.brightness
        if "temperature" in attrs_to_copy:
            self._temperature = color_temperature_mired_to_kelvin(other.color_temp)
        if "color" in attrs_to_copy:
            self._color = _rgb_list_to_int(other.rgb_color)

        return None

    @property
    def brightness(self):
        """Get the brightness recorded for this bulb."""
        return self._brightness

    @property
    def min_mireds(self):
        """Get the coldest color temperature supported by this kind of bulb."""
        warmest_color_temp_kelvins = self._remote.get_temperature_range()[1]
        coolest_color_temp_kelvins = self._remote.get_temperature_range()[0]
        warmest_color_temp_mired = color_temperature_kelvin_to_mired(
            warmest_color_temp_kelvins
        )
        coolest_color_temp_mired = color_temperature_kelvin_to_mired(
            coolest_color_temp_kelvins
        )
        min_color_temp_mired = min(warmest_color_temp_mired, coolest_color_temp_mired)
        return min_color_temp_mired

    @property
    def max_mireds(self):
        """Get the warmest color temperature supported by this kind of bulb."""
        warmest_color_temp_kelvins = self._remote.get_temperature_range()[1]
        coolest_color_temp_kelvins = self._remote.get_temperature_range()[0]
        warmest_color_temp_mired = color_temperature_kelvin_to_mired(
            warmest_color_temp_kelvins
        )
        coolest_color_temp_mired = color_temperature_kelvin_to_mired(
            coolest_color_temp_kelvins
        )
        max_color_temp_mired = max(warmest_color_temp_mired, coolest_color_temp_mired)
        return max_color_temp_mired

    @property
    def hs_color(self):
        """Get the current recorded color of the bulb as a (float(h), float(s)) tuple."""
        # HS color as an array of 2 floats
        r = (self._color >> 16) & 0xFF
        g = (self._color >> 8) & 0xFF
        b = self._color & 0xFF
        return color_RGB_to_hs(r, g, b)

    @property
    def rgb_color(self):
        """Get the current recorded color of the bulb as a (int(r), int(g), int(b)) tuple."""
        # RGB as an array of 3 ints
        r = (self._color >> 16) & 0xFF
        g = (self._color >> 8) & 0xFF
        b = self._color & 0xFF
        return [r, g, b]

    @property
    def color_temp(self):
        """Get the current recorded color temperature of the bulb."""
        # Color temperature in mired
        return color_temperature_kelvin_to_mired(self._temperature)

    @property
    def effect(self):
        """Stub: Incomplete: Get the current recorded effect."""
        return None

    @property
    def effect_list(self):
        """Stub: Incomplete: Get the list of effects supported by this bulb type."""
        return []

    # pylint: disable=arguments-differ
    def turn_off(self, **kwargs):
        """Turn off a bulb."""
        attrs_to_copy = ["state_on"]

        # If we already think the light state is off, don't bother
        # dimming the light.  This may be wrong when controlled by
        # manual remotes but will usually be correct.  Dimming
        # requires turning the bulb on, which kind of defeates the
        # purpose of turning the bulb off when it is already off.
        should_dim = self._state_on

        self._debug_log("Turning off")
        self._state_on = False
        self._brightness = 1

        if should_dim:
            attrs_to_copy.append("brightness")

        # Update all the child zones
        for child_zone in self._child_zones:
            child_zone.propagate_copy(self, attrs_to_copy)

        self._remote.off(self._zone, dim=should_dim)
        return None

    # pylint: disable=arguments-differ
    def turn_on(self, **kwargs):
        """Turn on and additionally modify some attributes of a bulb."""
        self._debug_log(f"Turning on with args = {kwargs}")
        self._state_on = True
        attrs_to_copy = ["state_on"]

        attr_brightness = kwargs.get(ATTR_BRIGHTNESS)
        attr_hs_color = kwargs.get(ATTR_HS_COLOR)
        attr_rgb_color = kwargs.get(ATTR_RGB_COLOR)
        attr_color_temp = kwargs.get(ATTR_COLOR_TEMP)

        # For now just record the brightness, we'll actually set it
        # after turning the bulb on
        if attr_brightness is not None:
            self._brightness = attr_brightness
            attrs_to_copy.append("brightness")

        if attr_hs_color is not None:
            attrs_to_copy.append("color")
            self._color = _rgb_list_to_int(
                color_hs_to_RGB(attr_hs_color[0], attr_hs_color[1])
            )

        if attr_rgb_color is not None:
            attrs_to_copy.append("color")
            self._color = _rgb_list_to_int(attr_rgb_color)

        if "color" in attrs_to_copy:
            if self._color == 0xFFFFFF:
                self._color = _rgb_list_to_int(
                    [self._brightness, self._brightness, self._brightness]
                )

        if attr_color_temp is not None:
            attrs_to_copy.append("temperature")
            self._temperature = color_temperature_mired_to_kelvin(attr_color_temp)
            self._debug_log(
                "Computed input temperature of {} mired to {} kelvin".format(
                    attr_color_temp, self._temperature
                )
            )

        self._remote.on(self._zone)

        # Apply the changes now that the bulb has been turned on
        if "brightness" in attrs_to_copy:
            self._remote.set_brightness(self._brightness, self._zone)

        if "temperature" in attrs_to_copy:
            self._remote.set_temperature(self._temperature, self._zone)

        if "color" in attrs_to_copy:
            self._remote.set_color(self._color, self._zone)

        # Update all the child zones
        for child_zone in self._child_zones:
            child_zone.propagate_copy(self, attrs_to_copy)

        return None

    def update(self):
        """Update attributes for this bulb.

        This only really makes the whole-remote entity on or off depending
        on whether any bulbs in any zones are recorded as being on/off.
        """
        if self._zone is None:
            child_zone_on = False
            for child_zone in self._child_zones:
                if child_zone.is_on:
                    child_zone_on = True
                    break

            self._state_on = child_zone_on
        return None
