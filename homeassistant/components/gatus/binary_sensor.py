"""Support for Gatus binary sensors."""

from collections.abc import Mapping
import logging
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[GatusDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gatus binary sensors based on a config entry."""
    coordinator = entry.runtime_data

    entities = [
        GatusEndpointBinarySensor(coordinator, entry, endpoint["key"])
        for endpoint in coordinator.data
        if "key" in endpoint
    ]

    async_add_entities(entities)


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

        endpoint_data = self._get_endpoint_data()
        group = endpoint_data.get("group", "Unknown").title()
        name = endpoint_data.get("name", "Unknown")

        self._attr_name = f"{group} {name}"
        self._attr_unique_id = f"{endpoint_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Gatus Server",
            manufacturer="TwiN",
            model="Gatus Monitoring Engine",
        )

    def _get_endpoint_data(self) -> dict:
        """Helper to safely extract this specific endpoint's data from the coordinator."""
        for endpoint in self.coordinator.data:
            if endpoint.get("key") == self._endpoint_key:
                return endpoint
        return {}

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the endpoint is up and healthy."""
        endpoint_data = self._get_endpoint_data()
        results = endpoint_data.get("results", [])

        if not results:
            return None

        latest_result = results[-1]
        return latest_result.get("success", False)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra operational attributes for the endpoint."""
        endpoint_data = self._get_endpoint_data()
        if not endpoint_data:
            return None

        results = endpoint_data.get("results", [])
        if not results:
            return None

        latest_result = results[-1]

        return {
            "hostname": latest_result.get("hostname"),
            "status_code": latest_result.get("status"),
            "duration_raw": latest_result.get("duration"),
            "timestamp": latest_result.get("timestamp"),
        }
