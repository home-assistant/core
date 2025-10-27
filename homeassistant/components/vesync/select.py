"""Support for VeSync numeric entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_humidifier, is_outlet, is_purifier
from .const import (
    DOMAIN,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
    HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF,
    OUTLET_NIGHT_LIGHT_LEVEL_AUTO,
    OUTLET_NIGHT_LIGHT_LEVEL_OFF,
    OUTLET_NIGHT_LIGHT_LEVEL_ON,
    PURIFIER_NIGHT_LIGHT_LEVEL_DIM,
    PURIFIER_NIGHT_LIGHT_LEVEL_OFF,
    PURIFIER_NIGHT_LIGHT_LEVEL_ON,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
    VS_MANAGER,
)
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

VS_TO_HA_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP = {
    100: HUMIDIFIER_NIGHT_LIGHT_LEVEL_BRIGHT,
    50: HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
    0: HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF,
}

HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP = {
    v: k for k, v in VS_TO_HA_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP.items()
}


@dataclass(frozen=True, kw_only=True)
class VeSyncSelectEntityDescription(SelectEntityDescription):
    """Class to describe a Vesync select entity."""

    exists_fn: Callable[[VeSyncBaseDevice], bool]
    current_option_fn: Callable[[VeSyncBaseDevice], str]
    select_option_fn: Callable[[VeSyncBaseDevice, str], Awaitable[bool]]


SELECT_DESCRIPTIONS: list[VeSyncSelectEntityDescription] = [
    # night_light for humidifier
    VeSyncSelectEntityDescription(
        key="night_light_level",
        translation_key="night_light_level",
        options=list(VS_TO_HA_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP.values()),
        icon="mdi:brightness-6",
        exists_fn=lambda device: is_humidifier(device) and device.supports_nightlight,
        # The select_option service framework ensures that only options specified are
        # accepted. ServiceValidationError gets raised for invalid value.
        select_option_fn=lambda device, value: device.set_nightlight_brightness(
            HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP.get(value, 0)
        ),
        # Reporting "off" as the choice for unhandled level.
        current_option_fn=lambda device: VS_TO_HA_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP.get(
            device.state.nightlight_brightness,
            HUMIDIFIER_NIGHT_LIGHT_LEVEL_OFF,
        ),
    ),
    # night_light for air purifiers
    VeSyncSelectEntityDescription(
        key="night_light_level",
        translation_key="night_light_level",
        options=[
            PURIFIER_NIGHT_LIGHT_LEVEL_OFF,
            PURIFIER_NIGHT_LIGHT_LEVEL_DIM,
            PURIFIER_NIGHT_LIGHT_LEVEL_ON,
        ],
        icon="mdi:brightness-6",
        exists_fn=lambda device: is_purifier(device) and device.supports_nightlight,
        select_option_fn=lambda device, value: device.set_nightlight_mode(value),
        current_option_fn=lambda device: device.state.nightlight_status,
    ),
    # night_light for outlets
    VeSyncSelectEntityDescription(
        key="night_light_level",
        translation_key="night_light_level",
        options=[
            OUTLET_NIGHT_LIGHT_LEVEL_OFF,
            OUTLET_NIGHT_LIGHT_LEVEL_ON,
            OUTLET_NIGHT_LIGHT_LEVEL_AUTO,
        ],
        icon="mdi:brightness-6",
        exists_fn=lambda device: is_outlet(device) and device.supports_nightlight,
        select_option_fn=lambda device, value: device.set_nightlight_state(value),
        current_option_fn=lambda device: device.state.nightlight_status,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        hass.data[DOMAIN][VS_MANAGER].devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
):
    """Add select entities."""

    async_add_entities(
        VeSyncSelectEntity(dev, description, coordinator)
        for dev in devices
        for description in SELECT_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncSelectEntity(VeSyncBaseEntity, SelectEntity):
    """A class to set numeric options on Vesync device."""

    entity_description: VeSyncSelectEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncSelectEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync select device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return an option."""
        return self.entity_description.current_option_fn(self.device)

    async def async_select_option(self, option: str) -> None:
        """Set an option."""
        if not await self.entity_description.select_option_fn(self.device, option):
            raise HomeAssistantError(self.device.last_response.message)
        await self.coordinator.async_request_refresh()
