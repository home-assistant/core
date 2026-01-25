"""NINA sensor platform."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_MESSAGE_SLOTS, CONF_REGIONS
from .coordinator import NinaConfigEntry, NINADataUpdateCoordinator
from .entity import NinaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NinaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NINA sensor platform."""

    coordinator = config_entry.runtime_data

    regions: dict[str, str] = config_entry.data[CONF_REGIONS]
    message_slots: int = config_entry.data[CONF_MESSAGE_SLOTS]

    async_add_entities(
        NinaHeadline(coordinator, ent, regions[ent], i + 1)
        for ent in coordinator.data
        for i in range(message_slots)
    )


class NinaHeadline(NinaEntity, SensorEntity):
    """Representation of a NINA headline."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        region_name: str,
        slot_id: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, region, slot_id)

        self._attr_name = f"Headline: {region_name} {slot_id}"
        self._attr_unique_id = f"{region_name}_{slot_id}-headline"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._active_warning_count > self._warning_index

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._get_warning_data().headline
