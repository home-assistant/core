"""EOL Tracker sensor integration for Home Assistant."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, cast

from aiohttp import ClientError
from eoltracker import EOLClient

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: Any = None,
) -> bool:
    """Set up EOL Tracker sensors from a config entry."""
    user_device_input = entry.data.get("input_device")
    session = async_get_clientsession(hass)
    client = EOLClient(session)

    async def async_fetch_data() -> dict[str, Any]:
        try:
            release_data = await client.fetch_release_data(user_device_input)
            product_data = await client.fetch_product_data(user_device_input)
        except ClientError as e:
            _LOGGER.error("Failed to fetch data from %s: %s", user_device_input, e)
            hass.async_create_task(
                hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": "EOL Tracker Error",
                        "message": f"Error fetching data for URI '{user_device_input}': {e}",
                    },
                )
            )
            return {}
        return {"release": release_data, "product": product_data}

    coordinator = DataUpdateCoordinator[dict[str, Any]](
        hass,
        _LOGGER,
        name="eol_tracker",
        update_method=async_fetch_data,
        update_interval=timedelta(seconds=300),
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data:
        _LOGGER.error("No data was received: aborting entity creation")
        return False

    data = coordinator.data
    release_info = data.get("release", {})
    product_info = data.get("product", {})

    label = release_info.get("label", "Unknown")
    product_name = product_info.get("label", "Unknown")
    entry_id = entry.entry_id

    entities: list[SensorEntity] = [
        EolSensor(coordinator, product_name, label, entry_id),
        BooleanEolSensor(
            coordinator,
            product_name,
            label,
            "LTS",
            cast(bool, release_info.get("isLts", False)),
            entry_id,
        ),
        BooleanEolSensor(
            coordinator,
            product_name,
            label,
            "EOL",
            cast(bool, release_info.get("isEol", False)),
            entry_id,
        ),
        BooleanEolSensor(
            coordinator,
            product_name,
            label,
            "Discontinued",
            cast(bool, release_info.get("isDiscontinued", False)),
            entry_id,
        ),
        BooleanEolSensor(
            coordinator,
            product_name,
            label,
            "Maintained",
            cast(bool, release_info.get("isMaintained", True)),
            entry_id,
        ),
    ]

    async_add_entities(entities)
    return True


class EolSensor(CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SensorEntity):
    """Representation of an EOL Tracker sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        name: str,
        product: str,
        entry_id: str,
    ) -> None:
        """Initialize the EolSensor."""
        super().__init__(coordinator)
        self._product = f"{name} {product}"
        self._attr_name = self._product
        self._attr_unique_id = f"{entry_id}_{product}".lower().replace(" ", "_")
        self._entry_id = entry_id

        self._attr_device_info = {
            "identifiers": {("eol", f"{entry_id}_{self._product}")},
            "name": f"{self._product} EOL",
            "manufacturer": "endoflife.date",
            "model": self._product,
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return SensorDeviceClass.TIMESTAMP

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture URL, if available."""
        return cast(
            str | None,
            self.coordinator.data.get("product", {}).get("links", {}).get("icon"),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        release_info = self.coordinator.data.get("release", {})
        product_info = self.coordinator.data.get("product", {})
        custom_attr = release_info.get("custom", {})

        supported_os = None
        if isinstance(custom_attr, dict):
            supported_os = next(iter(custom_attr.values()), None)

        return {
            "Release Date:": release_info.get("releaseDate", "Unknown"),
            "Latest:": release_info.get("latest", "Unknown"),
            "End of Life from:": release_info.get("eolFrom", "Unknown"),
            "endoflife.date link:": product_info.get("links", {}).get("html"),
            "Release Policy:": product_info.get("links", {}).get("releasePolicy"),
            "Supported OS Versions:": supported_os,
        }


class BooleanEolSensor(
    CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]], SensorEntity
):
    """Boolean attribute sensor for EOL Tracker."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        product_name: str,
        product: str,
        state: str,
        value: bool,
        entry_id: str,
    ) -> None:
        """Initialize the BooleanEolSensor."""
        super().__init__(coordinator)
        self._product = f"{product_name} {product}"
        self._state = state
        self._value = value
        self._attr_name = state
        self._attr_unique_id = (
            f"{entry_id}_{product_name}_{product}_{state}".lower().replace(" ", "_")
        )

        self._attr_icon = "mdi:check-circle" if value else "mdi:close-circle"
        self._attr_native_value = "Yes" if value else "No"

        self._attr_device_info = {
            "identifiers": {("eol", f"{entry_id}_{self._product}")},
            "name": f"{self._product} EOL",
            "manufacturer": "endoflife.date",
            "model": self._product,
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class, if any."""
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"name": self._attr_name}
