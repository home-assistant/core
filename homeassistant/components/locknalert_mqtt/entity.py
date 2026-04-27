"""Base LocknAlert entity classes."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import ATTR_BRIDGE_SERIAL, ATTR_FIRMWARE, ATTR_MODEL, DOMAIN


class LocknAlertEntity(Entity):
    """Common behavior and bridge device registry data."""

    _attr_should_poll = False

    def __init__(self, bridge_id: str, unique_key: str) -> None:
        self._bridge_id = bridge_id
        self._attr_unique_id = f"{bridge_id}_{unique_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._bridge_id)},
            manufacturer="LocknAlert",
            model=self.extra_state_attributes.get(ATTR_MODEL, "Bridge"),
            sw_version=self.extra_state_attributes.get(ATTR_FIRMWARE),
            name=f"LocknAlert Bridge {self._bridge_id}",
        )

    @property
    def available(self) -> bool:
        return bool(getattr(self, "_available", True))

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {ATTR_BRIDGE_SERIAL: self._bridge_id}
