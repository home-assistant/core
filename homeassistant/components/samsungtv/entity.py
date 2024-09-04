"""Base SamsungTV Entity."""

from __future__ import annotations

from wakeonlan import send_magic_packet

from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.trigger import PluggableAction
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MANUFACTURER, DOMAIN, LOGGER
from .coordinator import SamsungTVDataUpdateCoordinator
from .triggers.turn_on import async_get_turn_on_trigger


class SamsungTVEntity(CoordinatorEntity[SamsungTVDataUpdateCoordinator], Entity):
    """Defines a base SamsungTV entity."""

    _attr_has_entity_name = True

    def __init__(self, *, coordinator: SamsungTVDataUpdateCoordinator) -> None:
        """Initialize the SamsungTV entity."""
        super().__init__(coordinator)
        self._bridge = coordinator.bridge
        config_entry = coordinator.config_entry
        self._mac: str | None = config_entry.data.get(CONF_MAC)
        self._host: str | None = config_entry.data.get(CONF_HOST)
        # Fallback for legacy models that doesn't have a API to retrieve MAC or SerialNumber
        self._attr_unique_id = config_entry.unique_id or config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            name=config_entry.data.get(CONF_NAME),
            manufacturer=config_entry.data.get(CONF_MANUFACTURER),
            model=config_entry.data.get(CONF_MODEL),
        )
        if self.unique_id:
            self._attr_device_info[ATTR_IDENTIFIERS] = {(DOMAIN, self.unique_id)}
        if self._mac:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, self._mac)
            }
        self._turn_on_action = PluggableAction(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._bridge.auth_failed:
            return False
        return (
            self.coordinator.is_on
            or bool(self._turn_on_action)
            or self._mac is not None
            or self._bridge.power_off_in_progress
        )

    async def async_added_to_hass(self) -> None:
        """Connect and subscribe to dispatcher signals and state updates."""
        await super().async_added_to_hass()

        if (entry := self.registry_entry) and entry.device_id:
            self.async_on_remove(
                self._turn_on_action.async_register(
                    self.hass, async_get_turn_on_trigger(entry.device_id)
                )
            )

    def _wake_on_lan(self) -> None:
        """Wake the device via wake on lan."""
        send_magic_packet(self._mac, ip_address=self._host)
        # If the ip address changed since we last saw the device
        # broadcast a packet as well
        send_magic_packet(self._mac)

    async def _async_turn_off(self) -> None:
        """Turn the device off."""
        await self._bridge.async_power_off()
        await self.coordinator.async_refresh()

    async def _async_turn_on(self) -> None:
        """Turn the remote on."""
        if self._turn_on_action:
            LOGGER.debug("Attempting to turn on %s via automation", self.entity_id)
            await self._turn_on_action.async_run(self.hass, self._context)
        elif self._mac:
            LOGGER.info(
                "Attempting to turn on %s via Wake-On-Lan; if this does not work, "
                "please ensure that Wake-On-Lan is available for your device or use "
                "a turn_on automation",
                self.entity_id,
            )
            await self.hass.async_add_executor_job(self._wake_on_lan)
        else:
            LOGGER.error(
                "Unable to turn on %s, as it does not have an automation configured",
                self.entity_id,
            )
            raise HomeAssistantError(
                f"Entity {self.entity_id} does not support this service."
            )
