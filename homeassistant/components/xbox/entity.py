"""Base Sensor for the Xbox Integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from yarl import URL

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PresenceData, XboxUpdateCoordinator


class XboxBaseEntity(CoordinatorEntity[XboxUpdateCoordinator]):
    """Base Sensor for the Xbox Integration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XboxUpdateCoordinator,
        xuid: str,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize Xbox binary sensor."""
        super().__init__(coordinator)
        self.xuid = xuid
        self.entity_description = entity_description

        self._attr_unique_id = f"{xuid}_{entity_description.key}"
        if TYPE_CHECKING:
            assert self.data
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    "xbox_live"
                    if self.data.xuid == self.coordinator.client.xuid
                    else self.data.xuid,
                )
            },
            manufacturer="Microsoft",
            model="Xbox Network",
            name=self.data.gamertag,
        )

    @property
    def data(self) -> PresenceData | None:
        """Return coordinator data for this console."""
        return self.coordinator.data.presence.get(self.xuid)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.data is not None

    @property
    def entity_picture(self) -> str | None:
        """Return the gamer pic."""
        if not self.data:
            return None

        if self.entity_description.key != "online":
            return None
        # Xbox sometimes returns a domain that uses a wrong certificate which
        # creates issues with loading the image.
        # The correct domain is images-eds-ssl which can just be replaced
        # to point to the correct image, with the correct domain and certificate.
        # We need to also remove the 'mode=Padding' query because with it,
        # it results in an error 400.
        url = URL(self.data.display_pic)
        if url.host == "images-eds.xboxlive.com":
            url = url.with_host("images-eds-ssl.xboxlive.com").with_scheme("https")
        query = dict(url.query)
        query.pop("mode", None)
        return str(url.with_query(query))
