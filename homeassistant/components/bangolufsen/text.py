"""Text entities for the Bang & Olufsen integration."""


from __future__ import annotations

from mozart_api.models import HomeControlUri, ProductFriendlyName

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BangOlufsenEntity, EntityEnum, WebSocketNotification


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Text entities from config entry."""
    entities = []
    configuration = hass.data[DOMAIN][config_entry.unique_id]

    # Add Text entities.
    for text in configuration[EntityEnum.TEXT]:
        entities.append(text)

    async_add_entities(new_entities=entities)


class BangOlufsenText(TextEntity, BangOlufsenEntity):
    """Base Text class."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the Text."""
        super().__init__(entry)

        self._attr_entity_category = EntityCategory.CONFIG


class BangOlufsenTextFriendlyName(BangOlufsenText):
    """Friendly name Text."""

    def __init__(self, entry: ConfigEntry, friendly_name: str) -> None:
        """Init the friendly name Text."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Friendly name"
        self._attr_unique_id = f"{self._unique_id}-friendly-name"
        self._attr_icon = "mdi:id-card"

        self._attr_native_value = friendly_name

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self.entry.unique_id}_{WebSocketNotification.CONFIGURATION}",
                self._update_friendly_name,
            ),
        )

    async def async_set_value(self, value: str) -> None:
        """Set the friendly name."""
        self._attr_native_value = value
        self._client.set_product_friendly_name(
            product_friendly_name=ProductFriendlyName(friendly_name=value),
            async_req=True,
        )

    async def _update_friendly_name(self, _: str | None) -> None:
        """Update text value."""
        beolink_self = self._client.get_beolink_self(async_req=True).get()

        self._attr_native_value = beolink_self.friendly_name

        self.async_write_ha_state()


class BangOlufsenTextHomeControlUri(BangOlufsenText):
    """Home Control URI Text."""

    def __init__(self, entry: ConfigEntry, home_control_uri: str) -> None:
        """Init the Home Control URI Text."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Home Control URI"
        self._attr_unique_id = f"{self._unique_id}-home-control-uri"
        self._attr_icon = "mdi:link-variant"
        self._attr_native_value = home_control_uri
        self._attr_entity_registry_enabled_default = False

    async def async_set_value(self, value: str) -> None:
        """Set the Home Control URI name."""
        self._attr_native_value = value

        self._client.set_remote_home_control_uri(
            home_control_uri=HomeControlUri(uri=value), async_req=True
        )
