"""Support for Gatus binary sensors."""

from collections.abc import Mapping
from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GatusDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[GatusDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gatus binary sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        [
            GatusEndpointBinarySensor(coordinator, entry, endpoint["key"])
            for endpoint in coordinator.data
        ]
    )


class GatusEndpointBinarySensor(
    CoordinatorEntity[GatusDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Gatus endpoint status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: ConfigEntry,
        endpoint_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._endpoint_key = endpoint_key

        endpoint_data = self.endpoint_data
        if endpoint_data:
            group = endpoint_data.get("group", "Gatus")
            name = endpoint_data.get("name", endpoint_key)
        else:
            group = "Gatus Server"
            name = endpoint_key

        self._attr_name = f"{group} {name}"

        self._attr_unique_id = f"{entry.unique_id}_{endpoint_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Gatus Server",
        )

    @property
    def latest_result(self) -> dict | None:
        """Return the most recent monitoring result (Gatus appends newest last)."""
        if not (endpoint_data := self.endpoint_data):
            return None

        if not (results := endpoint_data["results"]):
            return None

        return results[-1]

    @property
    def endpoint_data(self) -> dict | None:
        """Return this specific endpoint's data from the coordinator."""
        return next(
            (ep for ep in self.coordinator.data if ep["key"] == self._endpoint_key),
            None,
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the endpoint is up and healthy."""
        if not (latest_result := self.latest_result):
            return None

        return latest_result.get("success", False)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra operational attributes for the endpoint."""
        if not (latest_result := self.latest_result):
            return None

        attributes: dict[str, Any] = {
            "hostname": latest_result["hostname"],
            "duration_raw": latest_result["duration"],
            "timestamp": latest_result["timestamp"],
            "success": latest_result["success"],
        }

        if "status" in latest_result:
            attributes["status_code"] = latest_result["status"]

        if "body" in latest_result:
            attributes["response_body"] = latest_result["body"]

        return attributes
