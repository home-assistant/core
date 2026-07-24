"""Switch entities — one Mesh panel = one device, multiple switch entities."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LanbonCoordinator


def _channel_name(dev: dict[str, Any] | None, index: int) -> str | None:
    if not dev:
        return None
    names = dev.get("channel_names") or []
    if isinstance(names, list) and index < len(names) and names[index]:
        text = str(names[index]).strip()
        return text or None
    return None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    api = entry.runtime_data.api

    entities: list[LanbonSwitch] = []
    for dev in (coordinator.data or {}).get("devices") or []:
        kind = dev.get("kind")
        switches = dev.get("switches")
        if not isinstance(switches, list):
            continue
        if kind not in ("switch", "cover_switch"):
            if kind != "cover_switch":
                continue
        mac = str(dev.get("mac") or "").upper()
        for idx, _val in enumerate(switches):
            entities.append(
                LanbonSwitch(
                    coordinator,
                    api,
                    mac,
                    idx,
                    _channel_name(dev, idx),
                    bool(dev.get("is_host")),
                )
            )
    async_add_entities(entities)


class LanbonSwitch(CoordinatorEntity[LanbonCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LanbonCoordinator,
        api,
        mac: str,
        index: int,
        channel_name: str | None,
        is_host: bool,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._mac = mac
        self._index = index
        self._attr_unique_id = f"{mac}_sw_{index}"
        self._attr_name = channel_name or f"Switch {index + 1}"
        self._suppress_registry_push = False
        hub_mac = ""
        host = (coordinator.data or {}).get("host") or {}
        hub_mac = str(host.get("mac") or "").upper()
        di_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, mac)},
            "manufacturer": "LANBON",
            "name": "LANBON Host" if is_host else f"LANBON {mac[-4:]}",
        }
        if (not is_host) and hub_mac:
            di_kwargs["via_device"] = (DOMAIN, hub_mac)
        self._attr_device_info = DeviceInfo(**di_kwargs)

    def _dev(self) -> dict[str, Any] | None:
        for d in (self.coordinator.data or {}).get("devices") or []:
            if str(d.get("mac") or "").upper() == self._mac:
                return d
        return None

    def _apply_channel_name(self, name: str | None) -> bool:
        """Update entity name from device; return True if changed."""
        new_name = name or f"Switch {self._index + 1}"
        if new_name == self._attr_name:
            return False
        self._attr_name = new_name
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        changed = self._apply_channel_name(_channel_name(self._dev(), self._index))
        if changed and self.entity_id:
            # Device is source of truth — mirror into entity registry (HA UI name)
            registry = er.async_get(self.hass)
            entry = registry.async_get(self.entity_id)
            if entry is not None and entry.name != self._attr_name:
                self._suppress_registry_push = True
                registry.async_update_entity(self.entity_id, name=self._attr_name)
                self._suppress_registry_push = False
        super()._handle_coordinator_update()

    async def async_set_channel_name(self, name: str) -> None:
        """HA → device rename."""
        await self._api.async_command(
            {
                "mac": self._mac,
                "op": "name_set",
                "index": self._index,
                "name": name,
            }
        )
        # Don't GET /devices immediately — root heap peaks after espnow; name already known
        self._attr_name = name
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        dev = self._dev()
        return bool(dev and dev.get("available", True))

    @property
    def is_on(self) -> bool | None:
        dev = self._dev()
        if not dev:
            return None
        switches = dev.get("switches") or []
        if self._index >= len(switches):
            return None
        return bool(switches[self._index])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._api.async_command(
            {"mac": self._mac, "op": "switch_set", "index": self._index, "on": True}
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._api.async_command(
            {"mac": self._mac, "op": "switch_set", "index": self._index, "on": False}
        )
        await self.coordinator.async_request_refresh()
