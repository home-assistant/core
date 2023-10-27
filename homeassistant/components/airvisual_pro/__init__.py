"""The AirVisual Pro integration."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pyairvisual.node import (
    InvalidAuthenticationError,
    NodeConnectionError,
    NodeProError,
    NodeSamba,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, LOGGER

PLATFORMS = [Platform.SENSOR]

UPDATE_INTERVAL = timedelta(minutes=1)


@dataclass
class AirVisualProData:
    """Define a data class."""

    coordinator: DataUpdateCoordinator
    node: NodeSamba


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AirVisual Pro from a config entry."""
    node = NodeSamba(entry.data[CONF_IP_ADDRESS], entry.data[CONF_PASSWORD])

    try:
        await node.async_connect()
    except NodeProError as err:
        raise ConfigEntryNotReady() from err

    reload_task: asyncio.Task | None = None

    async def async_get_data() -> dict[str, Any]:
        """Get data from the device."""
        try:
            data = await node.async_get_latest_measurements()
            data["history"] = {}
            if data["settings"].get("follow_mode") == "device":
                history = await node.async_get_history(include_trends=False)
                data["history"] = history.get("measurements", [])[-1]
        except InvalidAuthenticationError as err:
            raise ConfigEntryAuthFailed("Invalid Samba password") from err
        except NodeConnectionError as err:
            nonlocal reload_task
            if not reload_task:
                reload_task = hass.async_create_task(
                    hass.config_entries.async_reload(entry.entry_id)
                )
            raise UpdateFailed(f"Connection to Pro unit lost: {err}") from err
        except NodeProError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="Node/Pro data",
        update_interval=UPDATE_INTERVAL,
        update_method=async_get_data,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = AirVisualProData(
        coordinator=coordinator, node=node
    )

    async def async_shutdown(_: Event) -> None:
        """Define an event handler to disconnect from the websocket."""
        nonlocal reload_task
        if reload_task:
            with suppress(asyncio.CancelledError):
                reload_task.cancel()
        await node.async_disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data.node.async_disconnect()

    return unload_ok


class AirVisualProEntity(CoordinatorEntity):
    """Define a generic AirVisual Pro entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_unique_id = f"{coordinator.data['serial_number']}_{description.key}"
        self.entity_description = description

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data["serial_number"])},
            manufacturer="AirVisual",
            model=self.coordinator.data["status"]["model"],
            name=self.coordinator.data["settings"]["node_name"],
            hw_version=self.coordinator.data["status"]["system_version"],
            sw_version=self.coordinator.data["status"]["app_version"],
        )
