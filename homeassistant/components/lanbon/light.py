"""Light entities for dimmer panels."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LanbonCoordinator


def _ha_bri_from_dev(v: int) -> int:
    return max(0, min(255, int(round(v * 255 / 127)))) if v else 0


def _dev_bri_from_ha(v: int) -> int:
    return max(0, min(127, int(round(v * 127 / 255)))) if v else 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    api = entry.runtime_data.api
    entities = []
    for dev in (coordinator.data or {}).get("devices") or []:
        if dev.get("kind") != "light":
            continue
        mac = str(dev.get("mac") or "").upper()
        entities.append(LanbonLight(coordinator, api, mac, bool(dev.get("is_host"))))
    async_add_entities(entities)


class LanbonLight(CoordinatorEntity[LanbonCoordinator], LightEntity):
    _attr_has_entity_name = True
    _attr_name = "Dimmer"
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, coordinator, api, mac: str, is_host: bool) -> None:
        super().__init__(coordinator)
        self._api = api
        self._mac = mac
        self._attr_unique_id = f"{mac}_light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            manufacturer="LANBON",
            name="LANBON Host" if is_host else f"LANBON {mac[-4:]}",
        )

    def _dev(self):
        for d in (self.coordinator.data or {}).get("devices") or []:
            if str(d.get("mac") or "").upper() == self._mac:
                return d
        return None

    @property
    def available(self) -> bool:
        dev = self._dev()
        return bool(dev and dev.get("available", True))

    @property
    def is_on(self) -> bool | None:
        dev = self._dev()
        return None if not dev else bool(dev.get("on"))

    @property
    def brightness(self) -> int | None:
        dev = self._dev()
        if not dev:
            return None
        return _ha_bri_from_dev(int(dev.get("brightness") or 0))

    async def async_turn_on(self, **kwargs: Any) -> None:
        bri = kwargs.get(ATTR_BRIGHTNESS)
        payload: dict[str, Any] = {"mac": self._mac, "op": "light_set", "on": True}
        if bri is not None:
            payload["brightness"] = _dev_bri_from_ha(int(bri))
        await self._api.async_command(payload)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._api.async_command(
            {"mac": self._mac, "op": "light_set", "on": False, "brightness": 0}
        )
        await self.coordinator.async_request_refresh()
