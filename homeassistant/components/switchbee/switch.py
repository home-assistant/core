"""Support for SwitchBee switch."""
import logging

from switchbee.api import SwitchBeeError
from switchbee.device import ApiStateCommand, DeviceType, HardwareType

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbee switch."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        Device(hass, device, coordinator)
        for device in coordinator.data.values()
        if device.type in [DeviceType.TimedPowerSwitch, DeviceType.GroupSwitch]
    )


class Device(CoordinatorEntity, SwitchEntity):
    """Representation of an Switchbee switch."""

    def __init__(self, hass, device, coordinator):
        """Initialize the Switchbee switch."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = device.name
        self._device_id = device.id
        self._attr_unique_id = f"{self.coordinator.api.mac}-{device.id}"
        if device.hardware != HardwareType.Virtual:
            self._attr_device_info = DeviceInfo(
                identifiers={
                    (DOMAIN, self._attr_unique_id),
                },
                manufacturer="SwitchBee",
                model=device.type.display,
                suggested_area=device.zone,
                name=self.name,
            )
        self._attr_is_on = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # timed power switch state will represent a number of minutes until it goes off
        # regulare switches state is ON/OFF
        self._attr_is_on = (
            self.coordinator.data[self._device_id].state != ApiStateCommand.OFF
        )

        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs):
        """Async function to set on to switch."""
        return await self._async_set_state(ApiStateCommand.ON)

    async def async_turn_off(self, **kwargs):
        """Async function to set off to switch."""
        return await self._async_set_state(ApiStateCommand.OFF)

    async def _async_set_state(self, state):
        try:
            await self.coordinator.api.set_state(self._device_id, state)
        except SwitchBeeError as exp:
            _LOGGER.error(
                "Failed to set %s state %s, error: %s", self._attr_name, state, exp
            )
            self._async_write_ha_state()
        else:
            await self.coordinator.async_refresh()
