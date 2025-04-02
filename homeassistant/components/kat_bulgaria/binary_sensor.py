"""Support for KAT Bulgaria binary sensors."""

from kat_bulgaria.data_models import KatObligation

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import COORD_DATA_KEY
from .coordinator import KatBulgariaConfigEntry, KatBulgariaUpdateCoordinator
from .entity import KatBulgariaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KatBulgariaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up KAT Bulgaria fgbinary sensors based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        [
            KatBulgariaHasTicketsBinarySensor(coordinator),
            KatBulgariaHasNonServedTicketsBinarySensor(coordinator),
        ],
    )


class KatBulgariaHasTicketsBinarySensor(KatBulgariaEntity, BinarySensorEntity):
    """Defines a Total Ticket sensor."""

    _obligations: list[KatObligation]

    def __init__(self, coordinator: KatBulgariaUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._obligations = coordinator.data[COORD_DATA_KEY]
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_unique_id += "has_tickets"
        self._attr_translation_key = "has_tickets"

    @property
    def is_on(self) -> bool:
        """Return the state of the entity."""
        return len(self._obligations) != 0

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        return "mdi:cash-fast" if self.is_on else "mdi:cash-off"


class KatBulgariaHasNonServedTicketsBinarySensor(KatBulgariaEntity, BinarySensorEntity):
    """Defines a Non Served Ticket sensor."""

    _obligations: list[KatObligation]

    def __init__(self, coordinator: KatBulgariaUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._obligations = coordinator.data[COORD_DATA_KEY]
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_unique_id += "has_non_served_tickets"
        self._attr_translation_key = "has_non_served_tickets"

    @property
    def is_on(self) -> bool:
        """Return the state of the entity."""
        return (
            sum([obligation.is_served is False for obligation in self._obligations])
            != 0
        )

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        return "mdi:cash-fast" if self.is_on else "mdi:cash-off"
