"""Select platform for the Bring! integration."""

from __future__ import annotations

from bring_api import BringAuthException, BringParseException, BringRequestException
from bring_api.const import BRING_SUPPORTED_LOCALES

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BringConfigEntry
from .const import DOMAIN
from .entity import BringBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BringConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        BringListLanguageSelectEntity(
            coordinator,
            bring_list=bring_list,
        )
        for bring_list in coordinator.data.values()
    )


class BringListLanguageSelectEntity(BringBaseEntity, SelectEntity):
    """Bring language select entity."""

    entity_description = SelectEntityDescription(
        key="list_language",
        translation_key="list_language",
        entity_category=EntityCategory.CONFIG,
        options=BRING_SUPPORTED_LOCALES,
    )

    async def async_select_option(self, option: str) -> None:
        """Change the selected language."""
        try:
            await self.coordinator.bring.set_list_article_language(
                self._list_uuid, option
            )
        except (BringAuthException, BringRequestException, BringParseException) as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="set_language_request_failed"
            ) from e
        await self.coordinator.async_refresh_user_settings()
        await self.coordinator.async_refresh()

    @property
    def current_option(self) -> str | None:
        """Return selected language."""
        try:
            list_settings = next(
                filter(
                    lambda x: x["listUuid"] == self._list_uuid,
                    self.coordinator.user_settings["userlistsettings"],
                )
            )

            return next(
                filter(
                    lambda x: x["key"] == "listArticleLanguage",
                    list_settings["usersettings"],
                )
            )["value"]

        except (StopIteration, KeyError):
            return None
