"""Support for Twente Milieu sensors."""
from __future__ import annotations

from twentemilieu import (
    WASTE_TYPE_NON_RECYCLABLE,
    WASTE_TYPE_ORGANIC,
    WASTE_TYPE_PAPER,
    WASTE_TYPE_PLASTIC,
    TwenteMilieu,
    TwenteMilieuConnectionError,
)

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, DEVICE_CLASS_DATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_UPDATE, DOMAIN

PARALLEL_UPDATES = 1

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=WASTE_TYPE_NON_RECYCLABLE,
        name=f"{WASTE_TYPE_NON_RECYCLABLE} Waste Pickup",
        icon="mdi:delete-empty",
        device_class=DEVICE_CLASS_DATE,
    ),
    SensorEntityDescription(
        key=WASTE_TYPE_ORGANIC,
        name=f"{WASTE_TYPE_ORGANIC} Waste Pickup",
        icon="mdi:delete-empty",
        device_class=DEVICE_CLASS_DATE,
    ),
    SensorEntityDescription(
        key=WASTE_TYPE_PAPER,
        name=f"{WASTE_TYPE_PAPER} Waste Pickup",
        icon="mdi:delete-empty",
        device_class=DEVICE_CLASS_DATE,
    ),
    SensorEntityDescription(
        key=WASTE_TYPE_PLASTIC,
        name=f"{WASTE_TYPE_PLASTIC} Waste Pickup",
        icon="mdi:delete-empty",
        device_class=DEVICE_CLASS_DATE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twente Milieu sensor based on a config entry."""
    twentemilieu = hass.data[DOMAIN][entry.data[CONF_ID]]

    try:
        await twentemilieu.update()
    except TwenteMilieuConnectionError as exception:
        raise PlatformNotReady from exception

    async_add_entities(
        [
            TwenteMilieuSensor(twentemilieu, entry.data[CONF_ID], description)
            for description in SENSORS
        ],
        True,
    )


class TwenteMilieuSensor(SensorEntity):
    """Defines a Twente Milieu sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        twentemilieu: TwenteMilieu,
        unique_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Twente Milieu entity."""
        self.entity_description = description
        self._twentemilieu = twentemilieu
        self._attr_unique_id = f"{DOMAIN}_{unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Twente Milieu",
            name="Twente Milieu",
        )

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, DATA_UPDATE, self.async_schedule_update_ha_state
            )
        )

    async def async_update(self) -> None:
        """Update Twente Milieu entity."""
        next_pickup = await self._twentemilieu.next_pickup(self.entity_description.key)
        if next_pickup is not None:
            self._attr_native_value = next_pickup.date().isoformat()
