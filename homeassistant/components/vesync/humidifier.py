"""Support for VeSync humidifiers."""

import logging
from typing import Any

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
    VS_HUMIDIFIER_MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY,
    VS_HUMIDIFIER_MODE_MANUAL,
    VS_HUMIDIFIER_MODE_SLEEP,
    VS_MANAGER,
)
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)


MIN_HUMIDITY = 30
MAX_HUMIDITY = 80

VS_TO_HA_MODE_MAP = {
    VS_HUMIDIFIER_MODE_AUTO: MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY: MODE_AUTO,
    VS_HUMIDIFIER_MODE_MANUAL: MODE_NORMAL,
    VS_HUMIDIFIER_MODE_SLEEP: MODE_SLEEP,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        hass.data[DOMAIN][VS_MANAGER].devices.humidifiers,
        async_add_entities,
        coordinator,
    )


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
):
    """Add humidifier entities."""
    async_add_entities(VeSyncHumidifierHA(dev, coordinator) for dev in devices)


def _get_ha_mode(vs_mode: str) -> str | None:
    ha_mode = VS_TO_HA_MODE_MAP.get(vs_mode)
    if ha_mode is None:
        _LOGGER.warning("Unknown mode '%s'", vs_mode)
    return ha_mode


class VeSyncHumidifierHA(VeSyncBaseEntity, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    # The base VeSyncBaseEntity has _attr_has_entity_name and this is to follow the device name
    _attr_name = None

    _attr_max_humidity = MAX_HUMIDITY
    _attr_min_humidity = MIN_HUMIDITY
    _attr_supported_features = HumidifierEntityFeature.MODES

    # device: VeSyncHumidifierDevice

    def __init__(
        self,
        device: VeSyncBaseDevice,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSyncHumidifierHA device."""
        super().__init__(device, coordinator)

        # 2 Vesync humidifier modes (humidity and auto) maps to the HA mode auto.
        # They are on different devices though. We need to map HA mode to the
        # device specific mode when setting it.

        self._ha_to_vs_mode_map: dict[str, str] = {}
        self._available_modes: list[str] = []

        # Populate maps once.
        for vs_mode in self.device.mist_modes:
            ha_mode = _get_ha_mode(vs_mode)
            if ha_mode:
                self._available_modes.append(ha_mode)
                self._ha_to_vs_mode_map[ha_mode] = vs_mode

        self._available_modes.sort()

    def _get_vs_mode(self, ha_mode: str) -> str | None:
        return self._ha_to_vs_mode_map.get(ha_mode)

    @property
    def available_modes(self) -> list[str]:
        """Return the available mist modes."""
        return self._available_modes

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self.device.state.humidity

    @property
    def target_humidity(self) -> int:
        """Return the humidity we try to reach."""
        return self.device.state.auto_humidity

    @property
    def mode(self) -> str | None:
        """Get the current preset mode."""
        return (
            None
            if self.device.state.mode is None
            else _get_ha_mode(self.device.state.mode)
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity of the device."""
        if not await self.device.set_humidity(humidity):
            raise HomeAssistantError(
                f"An error occurred while setting humidity {humidity}."
            )

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the device."""
        if mode not in self.available_modes:
            raise HomeAssistantError(
                f"{mode} is not one of the valid available modes: {self.available_modes}"
            )
        if not await self.device.set_humidity_mode(self._get_vs_mode(mode)):
            raise HomeAssistantError(f"An error occurred while setting mode {mode}.")

        if mode == MODE_SLEEP:
            # We successfully changed the mode. Consider it a success even if display operation fails.
            await self.device.set_display(False)

        # Changing mode while humidifier is off actually turns it on, as per the app. But
        # the library does not seem to update the device_status. It is also possible that
        # other attributes get updated. Scheduling a forced refresh to get device status.
        # updated.
        self.schedule_update_ha_state(force_refresh=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        success = await self.device.turn_on()
        if not success:
            raise HomeAssistantError("An error occurred while turning on.")

        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        success = await self.device.turn_off()
        if not success:
            raise HomeAssistantError("An error occurred while turning off.")

        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.state.device_status == "on"
