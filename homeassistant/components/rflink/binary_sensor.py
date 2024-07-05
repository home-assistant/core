"""Support for Rflink binary sensors."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_DEVICES,
    CONF_FORCE_UPDATE,
    CONF_NAME,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.event as evt
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_ALIASES, RflinkDevice

CONF_OFF_DELAY = "off_delay"
DEFAULT_FORCE_UPDATE = False

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
                    vol.Optional(
                        CONF_FORCE_UPDATE, default=DEFAULT_FORCE_UPDATE
                    ): cv.boolean,
                    vol.Optional(CONF_OFF_DELAY): cv.positive_int,
                    vol.Optional(CONF_ALIASES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                }
            )
        }
    },
    extra=vol.ALLOW_EXTRA,
)


def devices_from_config(domain_config):
    """Parse configuration and add Rflink sensor devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device = RflinkBinarySensor(device_id, **config)
        devices.append(device)

    return devices


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config))


class RflinkBinarySensor(RflinkDevice, BinarySensorEntity, RestoreEntity):
    """Representation of an Rflink binary sensor."""

    def __init__(
        self,
        device_id: str,
        device_class: BinarySensorDeviceClass | None = None,
        force_update: bool = False,
        off_delay: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Handle sensor specific args and super init."""
        self._state = None
        self._attr_device_class = device_class
        self._attr_force_update = force_update
        self._off_delay = off_delay
        self._delay_listener = None
        super().__init__(device_id, **kwargs)

    async def async_added_to_hass(self) -> None:
        """Restore RFLink BinarySensor state."""
        await super().async_added_to_hass()
        if (old_state := await self.async_get_last_state()) is not None:
            if self._off_delay is None:
                self._state = old_state.state == STATE_ON
            else:
                self._state = False

    def _handle_event(self, event):
        """Domain specific event handler."""
        command = event["command"]
        if command in ["on", "allon"]:
            self._state = True
        elif command in ["off", "alloff"]:
            self._state = False

        if self._state and self._off_delay is not None:

            @callback
            def off_delay_listener(now):
                """Switch device off after a delay."""
                self._delay_listener = None
                self._state = False
                self.async_write_ha_state()

            if self._delay_listener is not None:
                self._delay_listener()
            self._delay_listener = evt.async_call_later(
                self.hass, self._off_delay, off_delay_listener
            )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state
