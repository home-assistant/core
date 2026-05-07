"""Base entity for Cloudflare Workers AI."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class CloudflareAIBaseEntity(Entity):
    """Base entity for Cloudflare Workers AI."""

    # Do NOT use has_entity_name=True here. This base entity keeps
    # entity.name as an explicit, non-None string by setting _attr_name
    # from the subentry title instead of relying on the device name.

    def __init__(
        self,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry,
        model_key: str,
    ) -> None:
        """Initialize the base entity.

        Args:
            config_entry: The integration config entry.
            subentry: The subentry this entity belongs to.
            model_key: The data key to read the model name from subentry.data.
        """
        self.entry = config_entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_name = subentry.title
        model_name = subentry.data.get(model_key, "unknown")
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Cloudflare",
            model=model_name,
            entry_type=dr.DeviceEntryType.SERVICE,
        )
