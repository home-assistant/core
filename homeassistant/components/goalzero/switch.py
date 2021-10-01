"""Support for Goal Zero Yeti Switches."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import Yeti, YetiEntity
from .const import DATA_KEY_API, DATA_KEY_COORDINATOR, DOMAIN

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="v12PortStatus",
        name="12V Port Status",
    ),
    SwitchEntityDescription(
        key="usbPortStatus",
        name="USB Port Status",
    ),
    SwitchEntityDescription(
        key="acPortStatus",
        name="AC Port Status",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Goal Zero Yeti switch."""
    name = entry.data[CONF_NAME]
    goalzero_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        YetiSwitch(
            goalzero_data[DATA_KEY_API],
            goalzero_data[DATA_KEY_COORDINATOR],
            name,
            description,
            entry.entry_id,
        )
        for description in SWITCH_TYPES
    )


class YetiSwitch(YetiEntity, SwitchEntity):
    """Representation of a Goal Zero Yeti switch."""

    def __init__(
        self,
        api: Yeti,
        coordinator: DataUpdateCoordinator,
        name: str,
        description: SwitchEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a Goal Zero Yeti switch."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

    @property
    def is_on(self) -> bool:
        """Return state of the switch."""
        return self.api.data.get(self.entity_description.key)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        payload = {self.entity_description.key: 0}
        await self.api.post_state(payload=payload)
        self.coordinator.async_set_updated_data(data=payload)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        payload = {self.entity_description.key: 1}
        await self.api.post_state(payload=payload)
        self.coordinator.async_set_updated_data(data=payload)
