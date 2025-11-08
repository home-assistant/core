"""Coordinator for the Switcher integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aioswitcher.api import SwitcherApi
from aioswitcher.device import (
    DeviceCategory,
    DeviceState,
    DeviceType,
    SwitcherBase,
    SwitcherLight,
    SwitcherPowerPlug,
    SwitcherShutter,
    SwitcherThermostat,
    SwitcherWaterHeater,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, update_coordinator
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    MANUAL_DEVICE_POLLING_INTERVAL_SEC,
    MAX_UPDATE_INTERVAL_SEC,
    SIGNAL_DEVICE_ADD,
)

_LOGGER = logging.getLogger(__name__)


class SwitcherDataUpdateCoordinator(
    update_coordinator.DataUpdateCoordinator[SwitcherBase]
):
    """Switcher device data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: SwitcherBase,
    ) -> None:
        """Initialize the Switcher device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=device.name,
            update_interval=timedelta(seconds=MAX_UPDATE_INTERVAL_SEC),
        )
        self.data = device
        self.token = entry.data.get(CONF_TOKEN)

    async def _async_update_data(self) -> SwitcherBase:
        """Mark device offline if no data."""
        raise update_coordinator.UpdateFailed(
            f"Device {self.name} did not send update for"
            f" {MAX_UPDATE_INTERVAL_SEC} seconds"
        )

    @property
    def model(self) -> str:
        """Switcher device model."""
        return self.data.device_type.value

    @property
    def device_id(self) -> str:
        """Switcher device id."""
        return self.data.device_id

    @property
    def mac_address(self) -> str:
        """Switcher device mac address."""
        return self.data.mac_address

    @callback
    def async_setup(self) -> None:
        """Set up the coordinator."""
        dev_reg = dr.async_get(self.hass)
        dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Switcher",
            name=self.name,
            model=self.model,
        )
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADD, self)


class SwitcherPollingDataUpdateCoordinator(
    update_coordinator.DataUpdateCoordinator[SwitcherBase]
):
    """Switcher device polling data update coordinator for manually configured devices."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        ip_address: str,
        device_id: str,
        device_key: str,
        device_type: DeviceType,
        token: str | None = None,
    ) -> None:
        """Initialize the Switcher polling device coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Switcher {device_id}",
            update_interval=timedelta(seconds=MANUAL_DEVICE_POLLING_INTERVAL_SEC),
        )
        self._ip_address = ip_address
        self._device_id = device_id
        self._device_key = device_key
        self._device_type = device_type
        self.token = token

    async def _async_update_data(self) -> SwitcherBase:
        """Fetch data from device via polling."""
        try:
            async with SwitcherApi(
                self._device_type,
                self._ip_address,
                self._device_id,
                self._device_key,
                self.token,
            ) as api:
                # Call the appropriate API method and create proper device object
                if self._device_type.category == DeviceCategory.THERMOSTAT:
                    response = await api.get_breeze_state()
                    if not response or not response.successful:
                        raise update_coordinator.UpdateFailed(
                            f"Failed to get state from device at {self._ip_address}"
                        )
                    # MAC address not available via TCP, use placeholder
                    return SwitcherThermostat(
                        device_type=self._device_type,
                        device_state=response.state,
                        device_id=self._device_id,
                        device_key=self._device_key,
                        ip_address=self._ip_address,
                        mac_address="",
                        name=self.name,
                        token_needed=self._device_type.token_needed,
                        mode=response.mode,
                        temperature=response.temperature,
                        target_temperature=response.target_temperature,
                        fan_level=response.fan_level,
                        swing=response.swing,
                        remote_id=response.remote_id,
                    )

                if self._device_type.category in (
                    DeviceCategory.SHUTTER,
                    DeviceCategory.SINGLE_SHUTTER_DUAL_LIGHT,
                    DeviceCategory.DUAL_SHUTTER_SINGLE_LIGHT,
                ):
                    response = await api.get_shutter_state(index=0)
                    if not response or not response.successful:
                        raise update_coordinator.UpdateFailed(
                            f"Failed to get state from device at {self._ip_address}"
                        )
                    return SwitcherShutter(
                        device_type=self._device_type,
                        device_state=DeviceState.OFF,
                        device_id=self._device_id,
                        device_key=self._device_key,
                        ip_address=self._ip_address,
                        mac_address="",
                        name=self.name,
                        token_needed=self._device_type.token_needed,
                        position=[response.position],
                        direction=[response.direction],
                        child_lock=[response.child_lock],
                    )

                if self._device_type.category == DeviceCategory.LIGHT:
                    response = await api.get_light_state(index=0)
                    if not response or not response.successful:
                        raise update_coordinator.UpdateFailed(
                            f"Failed to get state from device at {self._ip_address}"
                        )
                    return SwitcherLight(
                        device_type=self._device_type,
                        device_state=response.state,
                        device_id=self._device_id,
                        device_key=self._device_key,
                        ip_address=self._ip_address,
                        mac_address="",
                        name=self.name,
                        token_needed=self._device_type.token_needed,
                        light=[response.state],
                    )

                if self._device_type.category == DeviceCategory.POWER_PLUG:
                    response = await api.get_state()
                    if not response or not response.successful:
                        raise update_coordinator.UpdateFailed(
                            f"Failed to get state from device at {self._ip_address}"
                        )
                    return SwitcherPowerPlug(
                        device_type=self._device_type,
                        device_state=response.state,
                        device_id=self._device_id,
                        device_key=self._device_key,
                        ip_address=self._ip_address,
                        mac_address="",
                        name=self.name,
                        token_needed=self._device_type.token_needed,
                        power_consumption=response.power_consumption,
                        electric_current=response.electric_current,
                    )

                # Water heater devices
                response = await api.get_state()
                if not response or not response.successful:
                    raise update_coordinator.UpdateFailed(
                        f"Failed to get state from device at {self._ip_address}"
                    )
                return SwitcherWaterHeater(
                    device_type=self._device_type,
                    device_state=response.state,
                    device_id=self._device_id,
                    device_key=self._device_key,
                    ip_address=self._ip_address,
                    mac_address="",
                    name=self.name,
                    token_needed=self._device_type.token_needed,
                    remaining_time=response.time_left,
                    auto_shutdown=response.auto_shutdown,
                    power_consumption=response.power_consumption,
                    electric_current=response.electric_current,
                )

        except (TimeoutError, OSError, RuntimeError) as err:
            raise update_coordinator.UpdateFailed(
                f"Error communicating with device at {self._ip_address}: {err}"
            ) from err

    @property
    def model(self) -> str:
        """Switcher device model."""
        return self._device_type.value

    @property
    def device_id(self) -> str:
        """Switcher device id."""
        return self._device_id

    @property
    def mac_address(self) -> str:
        """Switcher device mac address."""
        return self.data.mac_address if self.data else ""

    @callback
    def async_setup(self) -> None:
        """Set up the coordinator."""
        dev_reg = dr.async_get(self.hass)
        # Don't register MAC connection for manual devices (not available via TCP)
        connections = set()
        if self.mac_address:
            connections.add((dr.CONNECTION_NETWORK_MAC, self.mac_address))

        dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            connections=connections,
            identifiers={(DOMAIN, self.device_id)},
            manufacturer="Switcher",
            name=self.name,
            model=self.model,
        )
        async_dispatcher_send(self.hass, SIGNAL_DEVICE_ADD, self)
