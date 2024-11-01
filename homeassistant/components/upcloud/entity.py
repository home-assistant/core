"""Support for UpCloud."""

from __future__ import annotations

import logging
from typing import Any

import upcloud_api

from homeassistant.const import CONF_USERNAME, STATE_OFF, STATE_ON, STATE_PROBLEM
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UpCloudDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ATTR_CORE_NUMBER = "core_number"
ATTR_HOSTNAME = "hostname"
ATTR_MEMORY_AMOUNT = "memory_amount"
ATTR_TITLE = "title"
ATTR_UUID = "uuid"
ATTR_ZONE = "zone"

DEFAULT_COMPONENT_NAME = "UpCloud {}"

STATE_MAP = {"error": STATE_PROBLEM, "started": STATE_ON, "stopped": STATE_OFF}


class UpCloudServerEntity(CoordinatorEntity[UpCloudDataUpdateCoordinator]):
    """Entity class for UpCloud servers."""

    def __init__(
        self,
        coordinator: UpCloudDataUpdateCoordinator,
        uuid: str,
    ) -> None:
        """Initialize the UpCloud server entity."""
        super().__init__(coordinator)
        self.uuid = uuid

    @property
    def _server(self) -> upcloud_api.Server:
        return self.coordinator.data[self.uuid]

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return self.uuid

    @property
    def name(self) -> str:
        """Return the name of the component."""
        try:
            return DEFAULT_COMPONENT_NAME.format(self._server.title)
        except (AttributeError, KeyError, TypeError):
            return DEFAULT_COMPONENT_NAME.format(self.uuid)

    @property
    def icon(self) -> str:
        """Return the icon of this server."""
        return "mdi:server" if self.is_on else "mdi:server-off"

    @property
    def is_on(self) -> bool:
        """Return true if the server is on."""
        try:
            return STATE_MAP.get(self._server.state, self._server.state) == STATE_ON  # type: ignore[no-any-return]
        except AttributeError:
            return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and STATE_MAP.get(
            self._server.state, self._server.state
        ) in (STATE_ON, STATE_OFF)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the UpCloud server."""
        return {
            x: getattr(self._server, x, None)
            for x in (
                ATTR_UUID,
                ATTR_TITLE,
                ATTR_HOSTNAME,
                ATTR_ZONE,
                ATTR_CORE_NUMBER,
                ATTR_MEMORY_AMOUNT,
            )
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return info for device registry."""
        assert self.coordinator.config_entry is not None
        return DeviceInfo(
            configuration_url="https://hub.upcloud.com",
            model="Control Panel",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (DOMAIN, f"{self.coordinator.config_entry.data[CONF_USERNAME]}@hub")
            },
            manufacturer="UpCloud Ltd",
        )
