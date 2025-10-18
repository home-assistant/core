"""Button platform for Sony Projector."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo  # type: ignore[attr-defined]
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SonyProjectorConfigEntry
from .const import CONF_MODEL, CONF_SERIAL, CONF_TITLE, DEFAULT_NAME, DOMAIN
from .coordinator import SonyProjectorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonyProjectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up projector buttons."""

    coordinator = entry.runtime_data.coordinator
    client = entry.runtime_data.client

    if coordinator.data is None:
        return

    identifier = entry.data.get(CONF_SERIAL) or entry.data[CONF_HOST]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        manufacturer="Sony",
        model=entry.data.get(CONF_MODEL),
        name=entry.data.get(CONF_TITLE, entry.title or DEFAULT_NAME),
    )

    async_add_entities(
        [SonyProjectorPictureMuteButton(entry, coordinator, client, device_info)]
    )


class SonyProjectorPictureMuteButton(
    CoordinatorEntity[SonyProjectorCoordinator], ButtonEntity
):
    """Button to toggle picture mute on the projector."""

    _attr_has_entity_name = True
    _attr_translation_key = "picture_mute"

    def __init__(self, entry, coordinator, client, device_info) -> None:
        """Initialize the button."""

        super().__init__(coordinator)
        self._client = client
        self._attr_device_info = device_info
        identifier = entry.data.get(CONF_SERIAL) or entry.data[CONF_HOST]
        self._attr_unique_id = f"{identifier}-picture_mute"

    @property
    def available(self) -> bool:
        """Return whether the projector is available."""

        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Handle button press to toggle picture mute."""

        await self._client.async_toggle_picture_mute()
        await self.coordinator.async_request_refresh()
