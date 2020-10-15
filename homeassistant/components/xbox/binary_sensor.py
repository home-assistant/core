"""Xbox friends binary sensors."""
from functools import partial
from typing import Dict, List, Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.entity_registry import (
    async_get_registry as async_get_entity_registry,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PresenceData, XboxUpdateCoordinator
from .const import DOMAIN

PRESENCE_ATTRIBUTES = ["online", "in_party", "in_game", "in_multiplayer"]


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    """Set up mysq covers."""
    coordinator: XboxUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    update_friends = partial(async_update_friends, coordinator, {}, async_add_entities)

    unsub = coordinator.async_add_listener(update_friends)
    hass.data[DOMAIN][config_entry.entry_id]["binary_sensor_unsub"] = unsub
    update_friends()


class XboxBinarySensorEntity(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Xbox presence state."""

    def __init__(self, coordinator: XboxUpdateCoordinator, xuid: str, attribute: str):
        """Initialize with API object, device id."""
        super().__init__(coordinator)
        self.xuid = xuid
        self.attribute = attribute

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self.xuid}_{self.attribute}"

    @property
    def data(self) -> PresenceData:
        """Return coordinator data for this console."""
        return self.coordinator.data.presence[self.xuid]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if self.attribute == "online":
            return self.data.gamertag

        attr_name = " ".join([part.title() for part in self.attribute.split("_")])
        return f"{self.data.gamertag} {attr_name}"

    @property
    def entity_picture(self) -> str:
        """Return the gamer pic."""
        return self.data.display_pic.replace("&mode=Padding", "")

    @property
    def is_on(self) -> bool:
        """Return the status of the requested attribute."""
        if not self.coordinator.last_update_success:
            return False
        return getattr(self.data, self.attribute)

    @property
    def device_state_attributes(self) -> Optional[Dict[str, str]]:
        """Return friend attributes."""
        if self.attribute != "online":
            return None

        return {
            "status": self.data.presence_text,
            "gamer_score": self.data.gamer_score,
            "account_tier": self.data.account_tier,
            "tenure": self.data.tenure,
        }

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.attribute == "online"

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, "xbox_live")},
            "name": "Xbox Live",
            "manufacturer": "Microsoft",
            "model": "Xbox Live",
            "entry_type": "service",
        }


@callback
def async_update_friends(
    coordinator: XboxUpdateCoordinator,
    current: Dict[str, List[XboxBinarySensorEntity]],
    async_add_entities,
) -> None:
    """Update friends."""
    new_ids = set(coordinator.data.presence)
    current_ids = set(current)

    # Process new favorites, add them to Home Assistant
    new_entities = []
    for xuid in new_ids - current_ids:
        current[xuid] = [
            XboxBinarySensorEntity(coordinator, xuid, attribute)
            for attribute in PRESENCE_ATTRIBUTES
        ]
        new_entities = new_entities + current[xuid]

    if new_entities:
        async_add_entities(new_entities)

    # Process deleted favorites, remove them from Home Assistant
    for xuid in current_ids - new_ids:
        coordinator.hass.async_create_task(
            async_remove_entities(xuid, coordinator, current)
        )


async def async_remove_entities(
    xuid: str,
    coordinator: XboxUpdateCoordinator,
    current: Dict[str, XboxBinarySensorEntity],
) -> None:
    """Remove WLED segment light from Home Assistant."""
    entities = current[xuid]
    for entity in entities:
        await entity.async_remove()
        registry = await async_get_entity_registry(coordinator.hass)
        if entity.entity_id in registry.entities:
            registry.async_remove(entity.entity_id)
    del current[xuid]
