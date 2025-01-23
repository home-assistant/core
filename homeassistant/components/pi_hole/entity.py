"""The pi_hole component."""

from __future__ import annotations

from hole import Hole

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class PiHoleEntity(CoordinatorEntity[DataUpdateCoordinator[None]]):
    """Representation of a Pi-hole entity."""

    def __init__(
        self,
        api: Hole,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize a Pi-hole entity."""
        super().__init__(coordinator)
        self.api = api
        self._name = name
        self._server_unique_id = server_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        if self.api.tls:
            config_url = f"https://{self.api.host}/{self.api.location}"
        else:
            config_url = f"http://{self.api.host}/{self.api.location}"

        return DeviceInfo(
            identifiers={(DOMAIN, self._server_unique_id)},
            name=self._name,
            manufacturer="Pi-hole",
            configuration_url=config_url,
        )
