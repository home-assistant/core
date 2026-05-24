"""Support for setting Deluge numeric configuration values."""

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DelugeNumberType, DelugeSensorType
from .coordinator import DelugeConfigEntry, DelugeDataUpdateCoordinator
from .entity import DelugeEntity

NUMBER_TYPES: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key=DelugeNumberType.LISTEN_PORT.value,
        translation_key=DelugeNumberType.LISTEN_PORT.value,
        native_min_value=1,
        native_max_value=65535,
        native_step=1,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DelugeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Deluge number entities."""
    async_add_entities(
        DelugeListenPortNumber(entry.runtime_data, description)
        for description in NUMBER_TYPES
    )


class DelugeListenPortNumber(DelugeEntity, NumberEntity):
    """Representation of the configured Deluge listen port."""

    entity_description: NumberEntityDescription

    def __init__(
        self,
        coordinator: DelugeDataUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{description.key}_config"
        )

    @property
    def native_value(self) -> float | None:
        """Return the configured listen port.

        Deluge stores listen_ports as [start_port, end_port]. For setting a single
        fixed port we use the start value as the displayed value.
        """
        listen_ports = self.coordinator.data[Platform.SENSOR].get(
            DelugeSensorType.LISTEN_PORTS_SENSOR.value
        )

        if isinstance(listen_ports, list | tuple) and listen_ports:
            return int(listen_ports[0])

        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the Deluge listen port."""
        await self.hass.async_add_executor_job(
            self.coordinator.set_listen_port,
            int(value),
        )
        await self.coordinator.async_request_refresh()
