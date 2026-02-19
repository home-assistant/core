"""Support for VeSync humidifiers."""

import logging
from typing import TYPE_CHECKING, Any

from pyvesync.base_devices.humidifier_base import VeSyncHumidifier

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_humidifier
from .const import (
    VS_DEVICES,
    VS_DISCOVERY,
    VS_HUMIDIFIER_MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY,
    VS_HUMIDIFIER_MODE_MANUAL,
    VS_HUMIDIFIER_MODE_SLEEP,
)
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)


VS_TO_HA_MODE_MAP = {
    VS_HUMIDIFIER_MODE_AUTO: MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY: VS_HUMIDIFIER_MODE_HUMIDITY,
    VS_HUMIDIFIER_MODE_MANUAL: MODE_NORMAL,
    VS_HUMIDIFIER_MODE_SLEEP: MODE_SLEEP,
}

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncHumidifier]) -> None:
        """Add new devices to platform."""
        _setup_entities(
            [dev for dev in devices if is_humidifier(dev)],
            async_add_entities,
            coordinator,
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        [
            dev
            for dev in config_entry.runtime_data.manager.devices.humidifiers
            if is_humidifier(dev)
        ],
        async_add_entities,
        coordinator,
    )


@callback
def _setup_entities(
    devices: list[VeSyncHumidifier],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Add humidifier entities."""
    async_add_entities(VeSyncHumidifierHA(dev, coordinator) for dev in devices)


def _get_ha_mode(vs_mode: str) -> str | None:
    ha_mode = VS_TO_HA_MODE_MAP.get(vs_mode)
    if ha_mode is None:
        _LOGGER.warning("Unknown mode '%s'", vs_mode)
    return ha_mode


class VeSyncHumidifierHA(VeSyncBaseEntity[VeSyncHumidifier], HumidifierEntity):
    """Representation of a VeSync humidifier."""

    # The base VeSyncBaseEntity has _attr_has_entity_name and this is to follow the device name
    _attr_name = None

    _attr_supported_features = HumidifierEntityFeature.MODES

    _attr_translation_key = "vesync"

    def __init__(
        self,
        device: VeSyncHumidifier,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSyncHumidifierHA device."""
        super().__init__(device, coordinator)

        # 2 Vesync humidifier modes (humidity and auto) maps to the HA mode auto.
        # They are on different devices though. We need to map HA mode to the
        # device specific mode when setting it.

        self._ha_to_vs_mode_map: dict[str, str] = {}
        self._available_modes: list[str] = []
        self._attr_max_humidity = max(device.target_minmax)
        self._attr_min_humidity = min(device.target_minmax)

        # Populate maps once.
        for vs_mode in self.device.mist_modes:
            ha_mode = _get_ha_mode(vs_mode)
            if ha_mode:
                self._available_modes.append(ha_mode)
                self._ha_to_vs_mode_map[ha_mode] = vs_mode

        self._available_modes.sort()

    def _get_vs_mode(self, ha_mode: str) -> str:
        return self._ha_to_vs_mode_map[ha_mode]

    @property
    def available_modes(self) -> list[str]:
        """Return the available mist modes."""
        return self._available_modes

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        if TYPE_CHECKING:
            assert self.device.state.humidity is not None
        return self.device.state.humidity

    @property
    def target_humidity(self) -> int:
        """Return the humidity we try to reach."""
        if TYPE_CHECKING:
            assert self.device.state.auto_humidity is not None
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
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Failed to set humidity.")

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the device."""
        if mode not in self.available_modes:
            raise HomeAssistantError(
                f"Invalid mode {mode}. Available modes: {self.available_modes}"
            )
        set_mode = self._get_vs_mode(mode)
        if set_mode is None:
            raise HomeAssistantError(f"Could not map mode {mode} to VeSync mode.")
        if not await self.device.set_mode(self._get_vs_mode(mode)):
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Failed to set mode.")

        if mode == MODE_SLEEP:
            # We successfully changed the mode. Consider it a success even if display operation fails.
            await self.device.toggle_display(False)

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        success = await self.device.turn_on()
        if not success:
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Failed to turn on humidifier.")

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        success = await self.device.turn_off()
        if not success:
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Failed to turn off humidifier.")

        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.state.device_status == "on"
