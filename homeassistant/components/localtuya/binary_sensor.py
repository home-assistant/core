"""Platform to present any Tuya DP as a binary sensor."""
import logging
from functools import partial

import voluptuous as vol
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS

from .common import LocalTuyaEntity, async_setup_entry

_LOGGER = logging.getLogger(__name__)

CONF_STATE_ON = "state_on"
CONF_STATE_OFF = "state_off"


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Required(CONF_STATE_ON, default="True"): str,
        vol.Required(CONF_STATE_OFF, default="False"): str,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }


class LocaltuyaBinarySensor(LocalTuyaEntity, BinarySensorEntity):
    """Representation of a Tuya binary sensor."""

    def __init__(
        self,
        device,
        config_entry,
        sensorid,
        **kwargs,
    ):
        """Initialize the Tuya binary sensor."""
        super().__init__(device, config_entry, sensorid, _LOGGER, **kwargs)
        self._is_on = False

    @property
    def is_on(self):
        """Return sensor state."""
        return self._is_on

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._config.get(CONF_DEVICE_CLASS)

    def status_updated(self):
        """Device status was updated."""
        state = str(self.dps(self._dp_id)).lower()
        if state == self._config[CONF_STATE_ON].lower():
            self._is_on = True
        elif state == self._config[CONF_STATE_OFF].lower():
            self._is_on = False
        else:
            self.warning(
                "State for entity %s did not match state patterns", self.entity_id
            )


async_setup_entry = partial(
    async_setup_entry, DOMAIN, LocaltuyaBinarySensor, flow_schema
)
