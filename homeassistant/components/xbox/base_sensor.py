"""Base Sensor for the Xbox Integration."""

from __future__ import annotations

from yarl import URL

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PresenceData, XboxUpdateCoordinator
from .const import DOMAIN


class XboxBaseSensorEntity(CoordinatorEntity[XboxUpdateCoordinator]):
    """Base Sensor for the Xbox Integration."""

    def __init__(
        self, coordinator: XboxUpdateCoordinator, xuid: str, attribute: str
    ) -> None:
        """Initialize Xbox binary sensor."""
        super().__init__(coordinator)
        self.xuid = xuid
        self.attribute = attribute
        self._attr_unique_id = f"{xuid}_{attribute}"
        self._attr_entity_registry_enabled_default = attribute == "online"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, "xbox_live")},
            manufacturer="Microsoft",
            model="Xbox Live",
            name="Xbox Live",
        )

    @property
    def data(self) -> PresenceData | None:
        """Return coordinator data for this console."""
        return self.coordinator.data.presence.get(self.xuid)

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        if not self.data:
            return None

        if self.attribute == "online":
            return self.data.gamertag

        attr_name = " ".join([part.title() for part in self.attribute.split("_")])
        return f"{self.data.gamertag} {attr_name}"

    @property
    def entity_picture(self) -> str | None:
        """Return the gamer pic."""
        if not self.data:
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
