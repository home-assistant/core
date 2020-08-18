"""Switch platform for FireServiceRota integration."""
import logging
from typing import Any, Dict

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, STATE_OFF, STATE_ON
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTRIBUTION, DOMAIN, SIGNAL_UPDATE_INCIDENTS, SWITCH_ENTITY_LIST

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up FireServiceRota switch based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    entry_id = entry.entry_id
    unique_id = entry.unique_id

    entities = []
    for (
        sensor_type,
        (name, unit, icon, device_class, enabled_by_default),
    ) in SWITCH_ENTITY_LIST.items():

        _LOGGER.debug(
            "Registering entity: %s, %s, %s, %s, %s, %s",
            sensor_type,
            name,
            unit,
            icon,
            device_class,
            enabled_by_default,
        )
        entities.append(
            ResponseSwitch(
                data,
                entry_id,
                unique_id,
                sensor_type,
                name,
                unit,
                icon,
                device_class,
                enabled_by_default,
            )
        )

    async_add_entities(entities, True)


class ResponseSwitch(SwitchEntity):
    """Representation of an FireServiceRota switch."""

    def __init__(
        self,
        data,
        entry_id,
        unique_id,
        sensor_type,
        name,
        unit,
        icon,
        device_class,
        enabled_default: bool = True,
    ):
        """Initialize."""
        self._data = data
        self._entry_id = entry_id
        self._unique_id = unique_id
        self._type = sensor_type
        self._name = name
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._enabled_default = enabled_default
        self._available = True

        self._state = None
        self._state_attributes = {}

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def is_on(self):
        """Get the assumed state of the switch."""
        return self._state

    @property
    def state(self):
        """Return the state of the switch."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this switch."""
        return f"{self._unique_id}_{self._type}"

    @property
    def device_state_attributes(self):
        """Return available attributes for switch."""
        attr = {}
        attr = self._state_attributes
        attr[ATTR_ATTRIBUTION] = ATTRIBUTION
        return attr

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": f"{self._name} Switch",
            "manufacturer": "FireServiceRota",
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_class(self):
        """Return the device class of the device."""
        return self._device_class

    async def async_turn_on(self, **kwargs) -> None:
        """Send Acknowlegde response status."""
        await self._data.async_set_response(self._data.incident_id, True)
        await self.async_update()

    async def async_turn_off(self, **kwargs) -> None:
        """Send Reject response status."""
        await self._data.async_set_response(self._data.incident_id, False)
        await self.async_update()

    @property
    def should_poll(self) -> bool:
        """Enable Polling for this switch."""
        return True

    async def async_added_to_hass(self):
        """Register update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATE_INCIDENTS}-{self._entry_id}",
                self.async_on_demand_update,
            )
        )

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Update FireServiceRota response data."""
        if not self.enabled:
            return

        await self._data.async_response_update()

        response_data = self._data.response_data
        if response_data:
            _LOGGER.debug("Incident response status: %s", response_data["status"])
            try:
                if response_data["status"] == "acknowledged":
                    self._state = STATE_ON
                else:
                    self._state = STATE_OFF

                del response_data["user_photo"]
                self._state_attributes = response_data
            except (KeyError, TypeError):
                pass

        _LOGGER.debug("Entity '%s' state set to: %s", self._name, self._state)
