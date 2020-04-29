"""Integration with the Rachio Iro sprinkler system controller."""
from abc import abstractmethod
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN as DOMAIN_RACHIO,
    KEY_DEVICE_ID,
    KEY_STATUS,
    KEY_SUBTYPE,
    SIGNAL_RACHIO_CONTROLLER_UPDATE,
    STATUS_OFFLINE,
    STATUS_ONLINE,
)
from .entity import RachioDevice
from .webhooks import SUBTYPE_COLD_REBOOT, SUBTYPE_OFFLINE, SUBTYPE_ONLINE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Rachio binary sensors."""
    entities = await hass.async_add_executor_job(_create_entities, hass, config_entry)
    async_add_entities(entities)
    _LOGGER.info("%d Rachio binary sensor(s) added", len(entities))


def _create_entities(hass, config_entry):
    entities = []
    for controller in hass.data[DOMAIN_RACHIO][config_entry.entry_id].controllers:
        entities.append(RachioControllerOnlineBinarySensor(controller))
    return entities


class RachioControllerBinarySensor(RachioDevice, BinarySensorEntity):
    """Represent a binary sensor that reflects a Rachio state."""

    def __init__(self, controller, poll=True):
        """Set up a new Rachio controller binary sensor."""
        super().__init__(controller)
        if poll:
            self._state = self._poll_update()
        else:
            self._state = None

    @property
    def is_on(self) -> bool:
        """Return whether the sensor has a 'true' value."""
        return self._state

    @callback
    def _async_handle_any_update(self, *args, **kwargs) -> None:
        """Determine whether an update event applies to this device."""
        if args[0][KEY_DEVICE_ID] != self._controller.controller_id:
            # For another device
            return

        # For this device
        self._async_handle_update(args, kwargs)

    @abstractmethod
    def _poll_update(self, data=None) -> bool:
        """Request the state from the API."""

    @abstractmethod
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle an update to the state of this sensor."""

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_RACHIO_CONTROLLER_UPDATE,
                self._async_handle_any_update,
            )
        )


class RachioControllerOnlineBinarySensor(RachioControllerBinarySensor):
    """Represent a binary sensor that reflects if the controller is online."""

    def __init__(self, controller):
        """Set up a new Rachio controller online binary sensor."""
        super().__init__(controller, poll=False)
        self._state = self._poll_update(controller.init_data)

    @property
    def name(self) -> str:
        """Return the name of this sensor including the controller name."""
        return self._controller.name

    @property
    def unique_id(self) -> str:
        """Return a unique id for this entity."""
        return f"{self._controller.controller_id}-online"

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY

    @property
    def icon(self) -> str:
        """Return the name of an icon for this sensor."""
        return "mdi:wifi-strength-4" if self.is_on else "mdi:wifi-strength-off-outline"

    def _poll_update(self, data=None) -> bool:
        """Request the state from the API."""
        if data is None:
            data = self._controller.rachio.device.get(self._controller.controller_id)[1]

        if data[KEY_STATUS] == STATUS_ONLINE:
            return True
        if data[KEY_STATUS] == STATUS_OFFLINE:
            return False
        _LOGGER.warning(
            '"%s" reported in unknown state "%s"', self.name, data[KEY_STATUS]
        )

    @callback
    def _async_handle_update(self, *args, **kwargs) -> None:
        """Handle an update to the state of this sensor."""
        if (
            args[0][0][KEY_SUBTYPE] == SUBTYPE_ONLINE
            or args[0][0][KEY_SUBTYPE] == SUBTYPE_COLD_REBOOT
        ):
            self._state = True
        elif args[0][0][KEY_SUBTYPE] == SUBTYPE_OFFLINE:
            self._state = False

        self.async_write_ha_state()
