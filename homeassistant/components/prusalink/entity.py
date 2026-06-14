"""The PrusaLink integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PrusaLinkUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class PrusaLinkEntityDescription(EntityDescription):
    """Base description for PrusaLink entities."""

    available_fn: Callable[[Any], bool] = lambda _: True
    supported_fn: Callable[[Any], bool] = lambda _: True


class PrusaLinkEntity(CoordinatorEntity[PrusaLinkUpdateCoordinator]):
    """Defines a base PrusaLink entity."""

    _attr_has_entity_name = True
    entity_description: PrusaLinkEntityDescription

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # `coordinator.data` can be None when the underlying endpoint
        # returns no payload — e.g. the job coordinator yields None when
        # no job is running on pyprusalink >= 3.0.0. Short-circuit to
        # avoid passing None into `available_fn` lambdas that assume a
        # dict (.get(), index, etc.).
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.available_fn(self.coordinator.data)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PrusaLink device."""
        coordinators = self.coordinator.config_entry.runtime_data
        info_data = coordinators["info"].data or {}
        version_data = coordinators["version"].data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=self.coordinator.config_entry.title,
            manufacturer="Prusa",
            serial_number=info_data.get("serial"),
            sw_version=version_data.get("firmware"),
            configuration_url=self.coordinator.api.client.host,
            suggested_area=info_data.get("location"),
        )
