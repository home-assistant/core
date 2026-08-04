"""KNX configuration storage controller for entity links."""

from typing import Any, NotRequired, TypedDict

from xknx import XKNX

from homeassistant.core import HomeAssistant, callback

from ..entity_link import KnxEntityLink


class KNXEntityLinkStoreConfigModel(TypedDict):
    """Represent a stored KNX entity link configuration."""

    entity_id: str
    platform: str
    channels: dict[str, dict[str, Any]]  # role: group address configuration
    notes: NotRequired[str]


type KNXEntityLinkStoreModel = dict[
    str, KNXEntityLinkStoreConfigModel
]  # entity_id: config


class EntityLinkController:
    """Controller managing UI-configured KNX entity links."""

    def __init__(self) -> None:
        """Initialize entity link controller."""
        self._links: dict[str, KnxEntityLink] = {}

    @callback
    def stop(self) -> None:
        """Shutdown entity link controller."""
        for link in self._links.values():
            link.async_remove()
        self._links.clear()

    @callback
    def start(
        self, hass: HomeAssistant, xknx: XKNX, config: KNXEntityLinkStoreModel
    ) -> None:
        """Set up all configured entity links."""
        if self._links:
            self.stop()
        for entity_id, link_config in config.items():
            self.update_link(hass, xknx, entity_id, link_config)

    @callback
    def update_link(
        self,
        hass: HomeAssistant,
        xknx: XKNX,
        entity_id: str,
        link_config: KNXEntityLinkStoreConfigModel,
    ) -> None:
        """Create or replace an entity link."""
        self.remove_link(entity_id)
        link = KnxEntityLink(
            hass,
            xknx,
            link_config["entity_id"],
            link_config["platform"],
            link_config["channels"],
        )
        self._links[entity_id] = link
        link.async_register()

    @callback
    def remove_link(self, entity_id: str) -> None:
        """Remove an entity link."""
        if entity_id in self._links:
            self._links.pop(entity_id).async_remove()
