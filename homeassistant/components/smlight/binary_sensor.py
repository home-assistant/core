"""Support for SLZB-06 binary sensors."""

from __future__ import annotations

from _collections_abc import Callable
from dataclasses import dataclass

from pysmlight import Sensors
from pysmlight.const import Events as SmEvents
from pysmlight.sse import MessageEvent

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SCAN_INTERNET_INTERVAL
from .coordinator import SmConfigEntry, SmDataUpdateCoordinator
from .entity import SmEntity

PARALLEL_UPDATES = 0
SCAN_INTERVAL = SCAN_INTERNET_INTERVAL


@dataclass(frozen=True, kw_only=True)
class SmBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing SMLIGHT binary sensor entities."""

    value_fn: Callable[[Sensors], bool]


SENSORS = [
    SmBinarySensorEntityDescription(
        key="ethernet",
        translation_key="ethernet",
        value_fn=lambda x: x.ethernet,
    ),
    SmBinarySensorEntityDescription(
        key="vpn",
        translation_key="vpn",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.vpn_status,
    ),
    SmBinarySensorEntityDescription(
        key="wifi",
        translation_key="wifi",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.wifi_connected,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMLIGHT sensor based on a config entry."""
    coordinator = entry.runtime_data.data

    async_add_entities(
        [
            *(
                SmBinarySensorEntity(coordinator, description)
                for description in SENSORS
            ),
            SmInternetSensorEntity(coordinator),
        ]
    )


class SmBinarySensorEntity(SmEntity, BinarySensorEntity):
    """Representation of a slzb binary sensor."""

    entity_description: SmBinarySensorEntityDescription
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmBinarySensorEntityDescription,
    ) -> None:
        """Initialize slzb binary sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.sensors)


class SmInternetSensorEntity(SmEntity, BinarySensorEntity):
    """Representation of the SLZB internet sensor."""

    _attr_translation_key = "internet"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
    ) -> None:
        """Initialize slzb binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.unique_id}_{self._attr_translation_key}"

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.client.sse.register_callback(
                SmEvents.EVENT_INET_STATE, self.internet_callback
            )
        )
        await self.async_update()

    @callback
    def internet_callback(self, event: MessageEvent) -> None:
        """Update internet state from event."""
        self._attr_is_on = event.data == "ok"
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Poll entity for internet connected updates."""
        return True

    async def async_update(self) -> None:
        """Update the sensor.

        This is an async api, device will respond with EVENT_INET_STATE event.
        """
        await self.coordinator.client.get_param("inetState")
