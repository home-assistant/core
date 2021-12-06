"""Support for Micropel."""
from abc import ABC
import logging
import typing
from typing import ClassVar

import voluptuous as vol

from homeassistant.components.cover import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_OFFSET,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_COMMUNICATOR_TYPE,
    CONF_CONNECTION_TCP,
    CONF_DATA_TYPE,
    CONF_PLC,
    CONF_PRECISION,
    CONF_REGISTER_TYPE,
    CONF_SCALE,
    DATA_TYPE_FLOAT,
    DATA_TYPE_INT,
    DOMAIN,
    REGISTER_TYPE_LONG_WORD,
    REGISTER_TYPE_WORD,
    SupportedPlatforms,
)
from .micropel import MicropelModule

_LOGGER = logging.getLogger(__name__)


class MicropelPlatformSchema(ABC):
    """Voluptuous schema for Micropel platform entity configuration."""

    PLATFORM_NAME: ClassVar[str]
    ENTITY_SCHEMA: ClassVar[vol.Schema]

    @classmethod
    def platform_node(cls) -> typing.Dict[vol.Optional, vol.All]:
        """Return a schema node for the platform."""
        return {
            vol.Optional(cls.PLATFORM_NAME): vol.All(
                cv.ensure_list, [cls.ENTITY_SCHEMA]
            )
        }


class SensorSchema(MicropelPlatformSchema):
    """Voluptuous schema for Micropel sensors."""

    PLATFORM_NAME = SupportedPlatforms.SENSOR.value

    ENTITY_SCHEMA = vol.All(
        vol.Schema(
            {
                vol.Optional(CONF_UNIQUE_ID): cv.string,
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_PLC): cv.positive_int,
                vol.Required(CONF_ADDRESS): cv.positive_int,
                vol.Optional(CONF_DATA_TYPE, default=DATA_TYPE_INT): vol.In(
                    [
                        DATA_TYPE_INT,
                        DATA_TYPE_FLOAT,
                    ]
                ),
                vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                vol.Optional(CONF_PRECISION, default=0): cv.positive_int,
                vol.Optional(CONF_REGISTER_TYPE, default=REGISTER_TYPE_WORD): vol.In(
                    [REGISTER_TYPE_WORD, REGISTER_TYPE_LONG_WORD]
                ),
                vol.Optional(CONF_SCALE, default=1): cv.positive_float,
                vol.Optional(CONF_OFFSET, default=0): cv.string,
                vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            }
        ),
    )


class ConnectionSchema:
    """Connection schema."""

    CONNECTION_TCP_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_COMMUNICATOR_TYPE): cv.string,
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_PORT): cv.port,
            vol.Required(CONF_PASSWORD): cv.positive_int,
        }
    )

    SCHEMA = {
        vol.Exclusive(CONF_CONNECTION_TCP, "connection_type"): CONNECTION_TCP_SCHEMA,
    }


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            vol.Schema(
                {
                    **ConnectionSchema.SCHEMA,
                    **SensorSchema.platform_node(),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up Micropel component."""
    try:
        micropel_module = MicropelModule(hass, config)
        hass.data[DOMAIN] = micropel_module
        await micropel_module.start()
    except Exception as ex:
        _LOGGER.warning("Could not connect to Micropel interface: %s", ex)
        hass.components.persistent_notification.async_create(
            f"Could not connect to Micropel interface: <br><b>{ex}</b>",
            title="Micropel",
        )

    for platform in SupportedPlatforms:
        if platform.value not in config[DOMAIN]:
            continue
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                platform.value,
                DOMAIN,
                {
                    "platform_config": config[DOMAIN][platform.value],
                },
                config,
            )
        )

    return True
