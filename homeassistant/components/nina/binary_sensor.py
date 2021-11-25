"""NINA sensor platform."""
from typing import Any, Dict, List

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_SAFETY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NINADataUpdateCoordinator
from .const import (
    ATTR_EXPIRES,
    ATTR_HEADLINE,
    ATTR_ID,
    ATTR_SENT,
    ATTR_START,
    CONF_FILTER_CORONA,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    CORONA_FILTER,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entries."""

    coordinator: NINADataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    filter_corona: bool = config_entry.data[CONF_FILTER_CORONA]
    regions: Dict[str, str] = config_entry.data[CONF_REGIONS]
    message_slots: int = config_entry.data[CONF_MESSAGE_SLOTS]

    entities: List[NINAMessage] = []

    for ent in coordinator.data:
        for i in range(0, message_slots):
            entities.append(
                NINAMessage(coordinator, ent, regions[ent], i + 1, filter_corona)
            )

    async_add_entities(entities)


class NINAMessage(CoordinatorEntity, BinarySensorEntity):
    """Representation of an NINA warning."""

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        regionName: str,
        slotID: int,
        filter_corona: bool,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._region: str = region
        self._region_name: str = regionName
        self._slot_id: int = slotID
        self._warning_index: int = slotID - 1

        self._filter_corona: bool = filter_corona

        self._coordinator: NINADataUpdateCoordinator = coordinator

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Warning: {self._region_name} {self._slot_id}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        if not len(self._coordinator.data[self._region]) > self._warning_index:
            return False

        data: Dict[str, Any] = self._coordinator.data[self._region][self._warning_index]

        return not (data[CORONA_FILTER] and self._filter_corona)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra attributes of the sensor."""
        if (
            not len(self._coordinator.data[self._region]) > self._warning_index
        ) or not self.is_on:
            return {}

        data: Dict[str, Any] = self._coordinator.data[self._region][self._warning_index]

        return {
            ATTR_HEADLINE: data[ATTR_HEADLINE],
            ATTR_ID: data[ATTR_ID],
            ATTR_SENT: data[ATTR_SENT],
            ATTR_START: data[ATTR_START],
            ATTR_EXPIRES: data[ATTR_EXPIRES],
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self._region}-{self._slot_id}"

    @property
    def device_class(self) -> str:
        """Return the device class of this entity."""
        return DEVICE_CLASS_SAFETY
