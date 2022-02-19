"""Support for Sensibo button."""
from __future__ import annotations

import asyncio

from aiohttp.client_exceptions import ClientConnectionError
import async_timeout
from pysensibo.exceptions import AuthenticationError, SensiboError

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, TIMEOUT
from .coordinator import SensiboDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sensibo buttons."""
    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboButton(coordinator, device_id)
        for device_id, device_data in coordinator.data.items()
        # Remove none climate devices
        if device_data["hvac_modes"] and device_data["temp"]
    )


class SensiboButton(CoordinatorEntity, ButtonEntity):
    """Representation of an SleepIQ button."""

    coordinator: SensiboDataUpdateCoordinator

    def __init__(
        self, coordinator: SensiboDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the Button."""
        super().__init__(coordinator)
        self._client = coordinator.client
        self._attr_name = f"{coordinator.data[device_id]['name']} On/Off"
        self._attr_unique_id = f"{device_id} on_off"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data[device_id]["id"])},
            name=coordinator.data[device_id]["name"],
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=coordinator.data[device_id]["model"],
            sw_version=coordinator.data[device_id]["fw_ver"],
            hw_version=coordinator.data[device_id]["fw_type"],
            suggested_area=coordinator.data[device_id]["name"],
        )

    async def async_press(self) -> None:
        """Press the On/Off button."""
        if self.coordinator.data[self.unique_id]["on"]:
            await self._async_set_ac_state_property("on", False)
        else:
            await self._async_set_ac_state_property("on", True)

    async def _async_set_ac_state_property(self, name: str, value: bool) -> None:
        """Set On/Off state."""
        result = {}
        try:
            async with async_timeout.timeout(TIMEOUT):
                result = await self._client.async_set_ac_state_property(
                    self.unique_id,
                    name,
                    value,
                    self.coordinator.data[self.unique_id]["ac_states"],
                    False,
                )
        except (
            ClientConnectionError,
            asyncio.TimeoutError,
            AuthenticationError,
            SensiboError,
        ) as err:
            raise HomeAssistantError(
                f"Failed to set AC state for device {self.name} to Sensibo servers: {err}"
            ) from err
        LOGGER.debug("Result: %s", result)

        if result["status"] == "Success":
            return
        failure = result["failureReason"]
        raise HomeAssistantError(
            f"Could not set state for device {self.name} due to reason {failure}"
        )
