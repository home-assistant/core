"""Support for LimitlessLED bulbs."""

import voluptuous

import homeassistant.components.limitlessled.light_rf as light_rf
import homeassistant.components.limitlessled.light_bridge as light_bridge

from homeassistant.components.light import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as config_validation

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

CONF_BRIDGES = "bridges"
CONF_GROUPS = "groups"
CONF_NUMBER = "number"
CONF_VERSION = "version"
CONF_FADE = "fade"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(light_bridge.CONF_BRIDGES): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(light_bridge.CONF_HOST): cv.string,
                    vol.Optional(
                        light_bridge.CONF_VERSION, default=light_bridge.DEFAULT_VERSION
                    ): cv.positive_int,
                    vol.Optional(light_bridge.CONF_PORT, default=light_bridge.DEFAULT_PORT): cv.port,
                    vol.Required(light_bridge.CONF_GROUPS): vol.All(
                        cv.ensure_list,
                        [
                            {
                                vol.Required(light_bridge.CONF_NAME): cv.string,
                                vol.Optional(
                                    light_bridge.CONF_TYPE, default=DEFAULT_LED_TYPE
                                ): vol.In(light_bridge.LED_TYPE),
                                vol.Required(light_bridge.CONF_NUMBER): cv.positive_int,
                                vol.Optional(
                                    light_bridge.CONF_FADE, default=light_bridge.DEFAULT_FADE
                                ): cv.boolean,
                            }
                        ],
                    ),
                }
            ],
        ),
        voluptuous.Optional(light_rf.CONF_RADIO_SECTION): voluptuous.All(
            {
                voluptuous.Optional(
                    light_rf.CONF_RADIO_GPIO_PIN
                ): config_validation.positive_int,
                voluptuous.Optional(light_rf.CONF_RADIO_SPI_BUS): config_validation.positive_int,
                voluptuous.Optional(light_rf.CONF_RADIO_SPI_DEV): config_validation.positive_int,
                voluptuous.Optional(light_rf.CONF_RADIO_TYPE): config_validation.string,
            }
        ),
        voluptuous.Optional(light_rf.CONF_REMOTE_RETRIES): config_validation.positive_int,
        voluptuous.Optional(light_rf.CONF_REMOTE_FORMAT): config_validation.match_all,
        voluptuous.Optional(light_rf.CONF_ZONE_FORMAT): config_validation.match_all,
        voluptuous.Optional(light_rf.CONF_REMOTES_SECTION): voluptuous.All(
            config_validation.ensure_list,
            [
                {
                    voluptuous.Optional(
                        light_rf.CONF_REMOTE_START
                    ): config_validation.positive_int,
                    voluptuous.Optional(light_rf.CONF_REMOTE_TYPE): config_validation.string,
                    voluptuous.Optional(
                        light_rf.CONF_REMOTE_COUNT
                    ): config_validation.positive_int,
                    voluptuous.Optional(
                        light_rf.CONF_REMOTE_ZONES
                    ): config_validation.ensure_list,
                    voluptuous.Optional(
                        light_rf.CONF_REMOTE_RETRIES
                    ): config_validation.positive_int,
                    voluptuous.Optional(
                        light_rf.CONF_REMOTE_FORMAT
                    ): config_validation.match_all,
                    voluptuous.Optional(light_rf.CONF_ZONE_FORMAT): config_validation.match_all,
                }
            ],
        ),
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Configure Home Assistant to be aware of all entities specified in the configuration file."""
    light_bridge.setup_platform(hass, config, add_entities, discovery_info = discovery_info)
    light_rf.setup_platform(hass, config, add_entities, discovery_info = discovery_info)
