"""Ecovacs image entities."""

from deebot_client.capabilities import CapabilityMap
from deebot_client.device import Device
from deebot_client.events.map import CachedMapInfoEvent, MapChangedEvent

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcovacsConfigEntry
from .entity import EcovacsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities = [
        EcovacsMap(device, caps, hass)
        for device in controller.devices
        if (caps := device.capabilities.map)
    ]

    if entities:
        async_add_entities(entities)


class EcovacsMap(
    EcovacsEntity[CapabilityMap],
    ImageEntity,
):
    """Ecovacs map."""

    _attr_content_type = "image/svg+xml"

    def __init__(
        self,
        device: Device,
        capability: CapabilityMap,
        hass: HomeAssistant,
    ) -> None:
        """Initialize entity."""
        super().__init__(device, capability, hass=hass)
        self._attr_extra_state_attributes = {}

    entity_description = EntityDescription(
        key="map",
        translation_key="map",
    )

    def image(self) -> bytes | None:
        """Return bytes of image or None."""
        if svg := self._device.map.get_svg_map():
            return svg.encode()

        return None

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_info(event: CachedMapInfoEvent) -> None:
            self._attr_extra_state_attributes["map_name"] = event.name

        async def on_changed(event: MapChangedEvent) -> None:
            self._attr_image_last_updated = event.when
            self.async_write_ha_state()

        self._subscribe(self._capability.cached_info.event, on_info)
        self._subscribe(self._capability.changed.event, on_changed)

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await super().async_update()
        self._device.map.refresh()
