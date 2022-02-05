"""Support for cybro lights."""
from __future__ import annotations

from typing import Any

from sqlalchemy import false

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AREA_LIGHTS,
    DEVICE_DESCRIPTION,
    DOMAIN,
    MANUFACTURER,
    MANUFACTURER_URL,
)
from .coordinator import CybroDataUpdateCoordinator
from .models import CybroEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cybro light based on a config entry."""
    coordinator: CybroDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # var_prefix = f"c{coordinator.cybro.nad}."
    lights = find_on_off_lights(coordinator)

    if lights is not None:
        async_add_entities(lights)


def find_on_off_lights(
    coordinator: CybroDataUpdateCoordinator,
) -> list[CybroUpdateLight] | None:
    """Find simple light objects in the plc vars.

    eg: c1000.lc00_qx00 and so on
    """
    res: list[CybroUpdateLight] = []
    for key in coordinator.data.plc_info.plc_vars:
        if key.find(".lc") != -1 and key.find("_qx") != -1:
            dev_info = DeviceInfo(
                # entry_type=DeviceEntryType.SERVICE,
                identifiers={(DOMAIN, key)},
                manufacturer=MANUFACTURER,
                # name=f"Light {key}",
                default_name=f"Light {key}",
                suggested_area=AREA_LIGHTS,
                model=f"{DEVICE_DESCRIPTION} Light Channel",
                configuration_url=MANUFACTURER_URL,
            )
            res.append(CybroUpdateLight(coordinator, key, dev_info=dev_info))

    if len(res) > 0:
        return res
    return None


class CybroUpdateLight(CybroEntity, LightEntity):
    """Defines a Simple Cybro light."""

    def __init__(
        self,
        coordinator: CybroDataUpdateCoordinator,
        var_name: str = "",
        attr_icon="mdi:lightbulb",
        dev_info: DeviceInfo = None,
    ) -> None:
        """Initialize Cybro light."""
        super().__init__(coordinator=coordinator)
        if var_name == "":
            return
        self._attr_unique_id = var_name
        self._attr_name = f"Light {var_name}"
        self._attr_icon = attr_icon
        self._attr_device_info = dev_info
        coordinator.data.add_var(self._attr_unique_id, var_type=0)

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None:
            return false
        return bool(res.value == "1")

    @property
    def available(self) -> bool:
        """Return if this light is available or not."""
        res = self.coordinator.data.vars.get(self._attr_unique_id, None)
        if res is None:
            return false
        return res.value != "?"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        await self.coordinator.cybro.write_var(self.unique_id, "0")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self.coordinator.cybro.write_var(self.unique_id, "1")
