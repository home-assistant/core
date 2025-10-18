"""Select platform for Sony Projector."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
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
    """Set up select entities from a config entry."""

    coordinator = entry.runtime_data.coordinator
    client = entry.runtime_data.client
    identifier = entry.data.get(CONF_SERIAL) or entry.data[CONF_HOST]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        manufacturer="Sony",
        model=entry.data.get(CONF_MODEL),
        name=entry.data.get(CONF_TITLE, entry.title or DEFAULT_NAME),
    )

    entities: list[SonyProjectorSelectBase] = []

    if coordinator.data and coordinator.data.aspect_ratio_options:
        entities.append(
            SonyProjectorAspectRatioSelect(entry, coordinator, client, device_info)
        )

    if coordinator.data and coordinator.data.picture_mode_options:
        entities.append(
            SonyProjectorPictureModeSelect(entry, coordinator, client, device_info)
        )

    if entities:
        async_add_entities(entities)


class SonyProjectorSelectBase(
    CoordinatorEntity[SonyProjectorCoordinator], SelectEntity
):
    """Base select entity for projector settings."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: SonyProjectorConfigEntry,
        coordinator,
        client,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the base select entity."""

        super().__init__(coordinator)
        self._entry = entry
        self._client = client
        self._attr_device_info = device_info

    def _identifier(self, suffix: str) -> str:
        identifier = self._entry.data.get(CONF_SERIAL) or self._entry.data[CONF_HOST]
        return f"{identifier}-{suffix}"


class SonyProjectorAspectRatioSelect(SonyProjectorSelectBase):
    """Select entity to adjust the projector aspect ratio."""

    _attr_translation_key = "aspect_ratio"

    def __init__(self, entry, coordinator, client, device_info) -> None:
        """Initialize the aspect ratio select entity."""

        super().__init__(entry, coordinator, client, device_info)
        self._attr_unique_id = self._identifier("aspect_ratio")

    @property
    def current_option(self) -> str | None:
        """Return the current aspect ratio option."""

        if (data := self.coordinator.data) is None:
            return None
        return data.aspect_ratio

    @property
    def options(self) -> list[str]:
        """Return available aspect ratios."""

        if (data := self.coordinator.data) is None:
            return []
        return data.aspect_ratio_options

    async def async_select_option(self, option: str) -> None:
        """Select a new aspect ratio."""

        await self._client.async_set_aspect_ratio(option)
        await self.coordinator.async_request_refresh()


class SonyProjectorPictureModeSelect(SonyProjectorSelectBase):
    """Select entity to adjust the projector picture mode."""

    _attr_translation_key = "picture_mode"

    def __init__(self, entry, coordinator, client, device_info) -> None:
        """Initialize the picture mode select entity."""

        super().__init__(entry, coordinator, client, device_info)
        self._attr_unique_id = self._identifier("picture_mode")

    @property
    def current_option(self) -> str | None:
        """Return the current picture mode option."""

        if (data := self.coordinator.data) is None:
            return None
        return data.picture_mode

    @property
    def options(self) -> list[str]:
        """Return available picture modes."""

        if (data := self.coordinator.data) is None:
            return []
        return data.picture_mode_options

    async def async_select_option(self, option: str) -> None:
        """Select a new picture mode."""

        await self._client.async_set_picture_mode(option)
        await self.coordinator.async_request_refresh()
