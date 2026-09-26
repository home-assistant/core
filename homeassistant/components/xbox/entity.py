"""Base Sensor for the Xbox Integration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, override

from pythonxbox.api.provider.people.models import Person
from pythonxbox.api.provider.smartglass.models import ConsoleType, SmartglassConsole
from pythonxbox.api.provider.titlehub.models import Title
from yarl import URL

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    ConsoleData,
    XboxConsoleStatusCoordinator,
    XboxPresenceCoordinator,
)

MAP_MODEL = {
    ConsoleType.XboxOne: "Xbox One",
    ConsoleType.XboxOneS: "Xbox One S",
    ConsoleType.XboxOneSDigital: "Xbox One S All-Digital",
    ConsoleType.XboxOneX: "Xbox One X",
    ConsoleType.XboxSeriesS: "Xbox Series S",
    ConsoleType.XboxSeriesX: "Xbox Series X",
}


@dataclass(kw_only=True, frozen=True)
class XboxBaseEntityDescription(EntityDescription):
    """Xbox base entity description."""

    entity_picture_fn: Callable[[Person, Title | None], str | None] | None = None
    attributes_fn: Callable[[Person, Title | None], Mapping[str, Any] | None] | None = (
        None
    )
    deprecated: bool | None = None


class XboxBaseEntity(CoordinatorEntity[XboxPresenceCoordinator]):
    """Base Sensor for the Xbox Integration."""

    _attr_has_entity_name = True
    entity_description: XboxBaseEntityDescription

    def __init__(
        self,
        coordinator: XboxPresenceCoordinator,
        xuid: str,
        entity_description: XboxBaseEntityDescription,
    ) -> None:
        """Initialize Xbox entity."""
        super().__init__(coordinator)
        self.xuid = xuid
        self.entity_description = entity_description

        self._attr_unique_id = f"{xuid}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, xuid)},
            manufacturer="Microsoft",
            model="Xbox Network",
            name=self.data.gamertag,
        )

    @property
    def data(self) -> Person:
        """Return coordinator data for this person."""
        return self.coordinator.data.presence[self.xuid]

    @property
    def title_info(self) -> Title | None:
        """Return title info."""
        return self.coordinator.data.title_info.get(self.xuid)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the entity picture."""

        return (
            entity_picture
            if self.available
            and (fn := self.entity_description.entity_picture_fn) is not None
            and (entity_picture := fn(self.data, self.title_info)) is not None
            else super().entity_picture
        )

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, float | None] | None:
        """Return entity specific state attributes."""
        return (
            fn(self.data, self.title_info)
            if (fn := self.entity_description.attributes_fn)
            else super().extra_state_attributes
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""

        return super().available and self.xuid in self.coordinator.data.presence


class XboxConsoleBaseEntity(CoordinatorEntity[XboxConsoleStatusCoordinator]):
    """Console base entity for the Xbox integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        console: SmartglassConsole,
        coordinator: XboxConsoleStatusCoordinator,
    ) -> None:
        """Initialize the Xbox Console entity."""

        super().__init__(coordinator, console)
        self.client = coordinator.client
        self._console = console

        self._attr_name = None
        self._attr_unique_id = console.id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, console.id)},
            manufacturer="Microsoft",
            model=MAP_MODEL.get(self._console.console_type),
            name=console.name,
        )

    @property
    def data(self) -> ConsoleData:
        """Return coordinator data for this console."""
        return self.coordinator.data[self._console.id]

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get(self._console.id) is not None


def to_https(image_url: str) -> str:
    """Convert image URLs to secure URLs."""

    url = URL(image_url)
    if url.host == "images-eds.xboxlive.com":
        url = url.with_host("images-eds-ssl.xboxlive.com")
    return str(url.with_scheme("https"))


def profile_pic(person: Person, _: Title | None = None) -> str | None:
    """Return the gamer pic."""

    # Xbox sometimes returns a domain that uses a wrong certificate which
    # creates issues with loading the image.
    # The correct domain is images-eds-ssl which can just be replaced
    # to point to the correct image, with the correct domain and certificate.
    # We need to also remove the 'mode=Padding' query because with it,
    # it results in an error 400.
    return str(URL(to_https(person.display_pic_raw)).without_query_params("mode"))


def entity_used_in(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get list of related automations and scripts."""
    used_in = automations_with_entity(hass, entity_id)
    used_in += scripts_with_entity(hass, entity_id)
    return used_in


def check_deprecated_entity(
    hass: HomeAssistant,
    xuid: str,
    entity_description: XboxBaseEntityDescription,
    entity_domain: str,
) -> bool:
    """Check for deprecated entity and remove it."""
    if not entity_description.deprecated:
        return True
    ent_reg = er.async_get(hass)
    if entity_id := ent_reg.async_get_entity_id(
        entity_domain,
        DOMAIN,
        f"{xuid}_{entity_description.key}",
    ):
        if (entity_entry := ent_reg.async_get(entity_id)) is not None:
            if entity_used_in(hass, entity_id) and not entity_entry.disabled:
                async_create_issue(
                    hass,
                    DOMAIN,
                    f"deprecated_entity_{xuid}_{entity_description.key}",
                    breaks_in_ha_version="2027.4.0",
                    is_fixable=True,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_entity",
                    translation_placeholders={
                        "name": str(entity_entry.name or entity_entry.original_name),
                        "entity": entity_id,
                    },
                    data={"entity_id": entity_id},
                )
                return True
            if not entity_used_in(hass, entity_id) or entity_entry.disabled:
                ent_reg.async_remove(entity_id)
                async_delete_issue(
                    hass,
                    DOMAIN,
                    f"deprecated_entity_{xuid}_{entity_description.key}",
                )

    return False
