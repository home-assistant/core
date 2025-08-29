"""Implementation of curtain devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import MyCurtainApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set the curtain entity."""
    client = MyCurtainApiClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    async def async_update_data():
        """Update device data and convert it into a dictionary structure."""
        devices = await client.get_devices()
        device_dict = {device["id"]: device for device in devices}
        _LOGGER.info(f"[Key] The coordinator obtains data.: {device_dict}")
        return device_dict

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="my_curtain_devices",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = []
    for device_id in coordinator.data:
        device_info = coordinator.data[device_id]
        entities.append(MyCurtainEntity(coordinator, client, device_info))

    async_add_entities(entities)


class MyCurtainEntity(CoordinatorEntity, CoverEntity)
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, coordinator, client, device) -> None:
        super().__init__(coordinator)
        self._client = client
        self._device_id = device["id"]
        self._attr_unique_id = f"my_curtain_{device['id']}"
        self._attr_name = device["name"]
        self._update_from_device(device)

    def _update_from_device(self, device):
        """Update the entity status from the device data."""
        _LOGGER.info("Update the entity status from the device data." + str(device))  # noqa: G003
        self._attr_current_cover_position = device["position"]
        self._attr_is_opening = device["state"] == "opening"
        self._attr_is_closing = device["state"] == "closing"
        self._attr_is_closed = device["is_closed"]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self.name,
            "manufacturer": "My Curtain",
            "model": "Smart Curtain",
        }

    @property
    def extra_state_attributes(self):
        device_data = self.coordinator.data.get(self._device_id, {})
        return {
            "device_id": self._device_id,
            "device_state": device_data.get("state", "unknown"),
        }

    @property
    def current_cover_position(self) -> int | None:
        """update the entity status from the device data.（0-100）."""
        return self.coordinator.data[self._device_id].get("position")

    @property
    def is_closed(self) -> bool:
        """Return whether the curtain is closed."""
        return self.coordinator.data[self._device_id].get("is_closed", False)

    @property
    def is_opening(self) -> bool:
        """Return whether the curtain is opening."""
        return self.coordinator.data[self._device_id].get("state") == "opening"

    @property
    def is_closing(self) -> bool:
        """Return whether the curtain is closing."""
        return self.coordinator.data[self._device_id].get("state") == "closing"

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the curtain."""
        _LOGGER.info("Open the curtain." + str(self))  # noqa: G003
        await self._client.set_device_position(self._device_id, 100)
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the curtain."""
        # _LOGGER.info("Close the curtain." + str(self))  # noqa: G003
        await self._client.set_device_position(self._device_id, 0)
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(5)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the curtain position."""
        position = kwargs.get(ATTR_POSITION)
        if position is not None:
            await self._client.set_device_position(self._device_id, position)
            await asyncio.sleep(5)
            await self.coordinator.async_request_refresh()
            await asyncio.sleep(5)
            await self.coordinator.async_request_refresh()
            await asyncio.sleep(5)
            await self.coordinator.async_request_refresh()
            await asyncio.sleep(5)
            await self.coordinator.async_request_refresh()
            await asyncio.sleep(5)
            await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
        await self.async_update()
