"""Definition and setup of the Omnilogic Binary Sensors for Home Assistant."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity

from .common import OmniLogicEntity, OmniLogicUpdateCoordinator
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    entities = []

    for item_id, item in coordinator.data.items():
        id_len = len(item_id)
        item_kind = item_id[-2]
        entity_settings = BINARY_SENSOR_TYPES.get((id_len, item_kind))
        
        if not entity_settings:
            continue

        for entity_setting in entity_settings:
            for state_key, entity_class in entity_setting["entity_classes"].items():
                if state_key not in item:
                    continue

                guard = False
                for guard_condition in entity_setting["guard_condition"]:
                    if guard_condition and all(
                        item.get(guard_key) == guard_value
                        for guard_key, guard_value in guard_condition.items()
                    ):
                        guard = True

                if guard:
                    continue

                entity = entity_class(
                    coordinator=coordinator,
                    state_key=state_key,
                    name=entity_setting["name"],
                    kind=entity_setting["kind"],
                    item_id=item_id,
                    device_class=entity_setting["device_class"],
                    icon=entity_setting["icon"],
                )

                entities.append(entity)

    async_add_entities(entities)


class OmnilogicSensor(OmniLogicEntity):
    """Defines an Omnilogic sensor entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        device_class: str,
        icon: str,
        item_id: tuple,
        state_key: str,
    ):
        """Initialize Entities."""
        super().__init__(
            coordinator=coordinator,
            kind=kind,
            name=name,
            item_id=item_id,
            icon=icon,
        )

        self._device_class = device_class
        self._state_key = state_key

    @property
    def device_class(self):
        """Return the device class of the entity."""
        return self._device_class


class OmniLogicAlarmSensor(OmnilogicSensor, BinarySensorEntity):
    """Define an OmniLogic Alarm Sensor."""

    @property
    def is_on(self):
        """Return the state for the alarm sensor."""
        alarms = len(self.coordinator.data[self._item_id][self._state_key]) > 0

        if alarms:
            _LOGGER.error(f"coord_data: {str(self.coordinator.data[self._item_id])}")
            self._attrs["alarm"] = self.coordinator.data[self._item_id]["Message"]
            self._attrs["alarm_comment"] = self.coordinator.data[self._item_id].get("Comment")
        else:
            self._attrs["alarm"] = "None"
            self._attrs["alarm_comment"] = ""

        return alarms


BINARY_SENSOR_TYPES = {
    (4, "Alarms"): [
        {
            "entity_classes": {"Severity": OmniLogicAlarmSensor},
            "name": "Alarm",
            "kind": "alarm",
            "device_class": None,
            "icon": "mdi:alarm-light",
            "guard_condition": [],
        }
    ]
}
