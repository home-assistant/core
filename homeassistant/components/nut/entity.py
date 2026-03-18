"""Base entity for the NUT integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import cast

from homeassistant.const import (
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import PyNUTData
from .const import DOMAIN

NUT_DEV_INFO_TO_DEV_INFO: dict[str, str] = {
    "manufacturer": ATTR_MANUFACTURER,
    "model": ATTR_MODEL,
    "firmware": ATTR_SW_VERSION,
    "serial": ATTR_SERIAL_NUMBER,
}


class NUTBaseEntity(CoordinatorEntity[DataUpdateCoordinator]):
    """NUT base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: EntityDescription,
        data: PyNUTData,
        unique_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"

        self.pynut_data = data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self.pynut_data.device_name,
        )
        self._attr_device_info.update(_get_nut_device_info(data))


def _get_nut_device_info(data: PyNUTData) -> DeviceInfo:
    """Return a DeviceInfo object filled with NUT device info."""
    nut_dev_infos = asdict(data.device_info)
    nut_infos = {
        info_key: nut_dev_infos[nut_key]
        for nut_key, info_key in NUT_DEV_INFO_TO_DEV_INFO.items()
        if nut_dev_infos[nut_key] is not None
    }

    return cast(DeviceInfo, nut_infos)
