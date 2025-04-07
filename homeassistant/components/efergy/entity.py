"""The Efergy integration."""

from __future__ import annotations

from pyefergy import Efergy

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DEFAULT_NAME, DOMAIN


class EfergyEntity(Entity):
    """Representation of a Efergy entity."""

    _attr_attribution = "Data provided by Efergy"

    def __init__(self, api: Efergy, server_unique_id: str) -> None:
        """Initialize an Efergy entity."""
        self.api = api
        self._attr_device_info = DeviceInfo(
            configuration_url="https://engage.efergy.com/user/login",
            connections={(dr.CONNECTION_NETWORK_MAC, api.info["mac"])},
            identifiers={(DOMAIN, server_unique_id)},
            manufacturer=DEFAULT_NAME,
            name=DEFAULT_NAME,
            model=api.info["type"],
            sw_version=api.info["version"],
        )
