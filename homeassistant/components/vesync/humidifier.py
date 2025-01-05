"""Support for VeSync humidifiers."""

from collections.abc import Mapping
import logging
from typing import Any

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import is_humidifier
from .const import (
    DOMAIN,
    VS_COORDINATOR,
    VS_DISCOVERY,
    VS_HUMIDIFIER_MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY,
    VS_HUMIDIFIER_MODE_MANUAL,
    VS_HUMIDIFIER_MODE_SLEEP,
    VS_HUMIDIFIERS,
    VeSyncHumidifierDevice,
)
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncDevice

_LOGGER = logging.getLogger(__name__)


MIN_HUMIDITY = 30
MAX_HUMIDITY = 80

VS_TO_HA_ATTRIBUTES = {ATTR_HUMIDITY: "current_humidity"}

VS_TO_HA_MODE_MAP = {
    VS_HUMIDIFIER_MODE_AUTO: MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY: MODE_AUTO,
    VS_HUMIDIFIER_MODE_MANUAL: MODE_NORMAL,
    VS_HUMIDIFIER_MODE_SLEEP: MODE_SLEEP,
}

HA_TO_VS_MODE_MAP = {v: k for k, v in VS_TO_HA_MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_HUMIDIFIERS], async_add_entities, coordinator)


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities,
    coordinator: VeSyncDataCoordinator,
):
    """Add humidifier entities."""
    entities = [
        VeSyncHumidifierHA(dev, coordinator) for dev in devices if is_humidifier(dev)
    ]

    async_add_entities(entities, update_before_add=True)


def _get_ha_mode(vs_mode: str) -> str | None:
    ha_mode = VS_TO_HA_MODE_MAP.get(vs_mode)
    if ha_mode is None:
        _LOGGER.warning("Unknown mode '%s'", vs_mode)
    return ha_mode


def _get_vs_mode(ha_mode: str) -> str | None:
    vs_mode = HA_TO_VS_MODE_MAP.get(ha_mode)
    if vs_mode is None:
        _LOGGER.warning("Unknown mode '%s'", ha_mode)
    return vs_mode


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    _attr_max_humidity = MAX_HUMIDITY
    _attr_min_humidity = MIN_HUMIDITY
    _attr_supported_features: HumidifierEntityFeature = HumidifierEntityFeature(
        HumidifierEntityFeature.MODES
    )

    def __init__(
        self,
        humidifier: VeSyncHumidifierDevice,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier, coordinator)
        self.smarthumidifier = humidifier

    @property
    def available_modes(self) -> list[str]:
        """Return the available mist modes."""
        return [
            ha_mode
            for ha_mode in (
                _get_ha_mode(vs_mode) for vs_mode in self.smarthumidifier.mist_modes
            )
            if ha_mode
        ]

    @property
    def target_humidity(self) -> int:
        """Return the humidity we try to reach."""
        return self.smarthumidifier.config["auto_target_humidity"]

    @property
    def mode(self) -> str | None:
        """Get the current preset mode."""
        return _get_ha_mode(self.smarthumidifier.details["mode"])

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes of the humidifier."""

        attr = {}
        for k, v in self.smarthumidifier.details.items():
            if k in VS_TO_HA_ATTRIBUTES:
                attr[VS_TO_HA_ATTRIBUTES[k]] = v
            elif k in self.state_attributes:
                attr[f"vs_{k}"] = v
            else:
                attr[k] = v
        return attr

    def set_humidity(self, humidity: int) -> None:
        """Set the target humidity of the device."""
        if humidity not in range(int(self.min_humidity), int(self.max_humidity + 1)):
            raise ValueError(
                "{humidity} is not between {self.min_humidity} and {self.max_humidity} (inclusive)"
            )
        if self.smarthumidifier.set_humidity(humidity):
            self.schedule_update_ha_state()
        else:
            raise ValueError("An error occurred while setting humidity.")

    def set_mode(self, mode: str) -> None:
        """Set the mode of the device."""
        if mode not in self.available_modes:
            raise ValueError(
                "{mode} is not one of the valid available modes: {self.available_modes}"
            )
        if self.smarthumidifier.set_humidity_mode(_get_vs_mode(mode)):
            self.schedule_update_ha_state()
        else:
            raise ValueError("An error occurred while setting mode.")

    def turn_on(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        success = self.smarthumidifier.turn_on()
        if not success:
            raise ValueError("An error occurred while turning on.")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        success = self.smarthumidifier.turn_off()
        if not success:
            raise ValueError("An error occurred while turning off.")
