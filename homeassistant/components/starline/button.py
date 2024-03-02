"""Support for StarLine button."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

BUTTON_TYPES: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="poke",
        translation_key="horn",
        icon="mdi:bullhorn-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the StarLine button."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        if device.support_state:
            for description in BUTTON_TYPES:
                entities.append(StarlineButton(account, device, description))
    async_add_entities(entities)


class StarlineButton(StarlineEntity, ButtonEntity):
    """Representation of a StarLine button."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(account, device, description.key)
        self.entity_description = description

    @property
    def available(self):
        """Return True if entity is available."""
        return super().available and self._device.online

    def press(self):
        """Press the button."""
        self._account.api.set_car_state(self._device.device_id, self._key, True)
