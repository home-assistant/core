"""Support for SwitchBee switch."""
import logging
from typing import Any

from switchbee import SWITCHBEE_BRAND
from switchbee.api import SwitchBeeDeviceOfflineError, SwitchBeeError
from switchbee.device import ApiStateCommand, DeviceType, SwitchBeeBaseDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbee switch."""
    coordinator: SwitchBeeCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SwitchBeeSwitchEntity(device, coordinator)
        for device in coordinator.data.values()
        if device.type
        in [
            DeviceType.TimedPowerSwitch,
            DeviceType.GroupSwitch,
            DeviceType.Switch,
            DeviceType.TimedSwitch,
        ]
    )


class SwitchBeeSwitchEntity(CoordinatorEntity[SwitchBeeCoordinator], SwitchEntity):
    """Representation of an Switchbee switch."""

    def __init__(
        self,
        device: SwitchBeeBaseDevice,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee switch."""
        super().__init__(coordinator)
        self._attr_name = f"{device.name}"
        self._device_id = device.id
        self._attr_unique_id = f"{coordinator.mac_formated}-{device.id}"
        self._attr_is_on = False
        self._is_online = True
        self._attr_has_entity_name = True
        self._device = device
        self._attr_device_info = DeviceInfo(
            name=f"SwitchBee_{str(device.unit_id)}",
            identifiers={
                (
                    DOMAIN,
                    f"{str(device.unit_id)}-{coordinator.mac_formated}",
                )
            },
            manufacturer=SWITCHBEE_BRAND,
            model=coordinator.api.module_display(device.unit_id),
            suggested_area=device.zone,
            via_device=(
                DOMAIN,
                f"{coordinator.api.name} ({coordinator.api.mac})",
            ),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_online and super().available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        super()._handle_coordinator_update()

    def _update_from_coordinator(self) -> None:
        """Update the entity attributes from the coordinator data."""

        async def async_refresh_state():
            """Refresh the device state in the Central Unit.

            This function addresses issue of a device that came online back but still report
            unavailable state (-1).
            Such device (offline device) will keep reporting unavailable state (-1)
            until it has been actuated by the user (state changed to on/off).

            With this code we keep trying setting dummy state for the device
            in order for it to start reporting its real state back (assuming it came back online)

            """

            try:
                await self.coordinator.api.set_state(self._device_id, "dummy")
            except SwitchBeeDeviceOfflineError:
                return
            except SwitchBeeError:
                return

        if self.coordinator.data[self._device_id].state == -1:
            # This specific call will refresh the state of the device in the CU
            self.hass.async_create_task(async_refresh_state())

            # if the device was online (now offline), log message and mark it as Unavailable
            if self._is_online:
                _LOGGER.error(
                    "%s switch is not responding, check the status in the SwitchBee mobile app",
                    self.name,
                )
                self._is_online = False

            return

        # check if the device was offline (now online) and bring it back
        if not self._is_online:
            _LOGGER.info(
                "%s switch is now responding",
                self.name,
            )
            self._is_online = True

        # timed power switch state is an integer representing the number of minutes left until it goes off
        # regulare switches state is ON/OFF (1/0 respectively)
        self._attr_is_on = (
            self.coordinator.data[self._device_id].state != ApiStateCommand.OFF
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async function to set on to switch."""
        return await self._async_set_state(ApiStateCommand.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Async function to set off to switch."""
        return await self._async_set_state(ApiStateCommand.OFF)

    async def _async_set_state(self, state: ApiStateCommand) -> None:
        try:
            await self.coordinator.api.set_state(self._device_id, state)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            await self.coordinator.async_refresh()
            raise HomeAssistantError(
                f"Failed to set {self._attr_name} state {state}, {str(exp)}"
            ) from exp

        await self.coordinator.async_refresh()
