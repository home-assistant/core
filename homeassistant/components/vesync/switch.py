"""Support for VeSync switches."""
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from pyvesync.vesyncfan import VeSyncAirBypass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncBaseEntity, VeSyncDevice
from .const import DEV_TYPE_TO_HA, DOMAIN, SKU_TO_BASE_DEVICE, VS_DISCOVERY, VS_SWITCHES

_LOGGER = logging.getLogger(__name__)

DISPLAY_SUPPORTED = ["Vital200S"]
CHILD_LOCK_SUPPORTED = ["Vital200S"]
LIGHT_MODE_SUPPORTED = ["Vital200S"]


def sku_supported(device, supported):
    """Get the base device of which a device is an instance."""
    return SKU_TO_BASE_DEVICE.get(device.device_type) in supported


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_SWITCHES), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_SWITCHES], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "outlet":
            entities.append(VeSyncSwitchHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "switch":
            entities.append(VeSyncLightSwitch(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "fan":
            for description in FAN_SWITCHES:
                if description.exists_fn(dev):
                    entities.append(VeSyncFanSwitchEntity(dev, description))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseSwitch(VeSyncDevice, SwitchEntity):
    """Base class for VeSync switch Device Representations."""

    _attr_name = None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.device.turn_on()


class VeSyncSwitchHA(VeSyncBaseSwitch, SwitchEntity):
    """Representation of a VeSync switch."""

    def __init__(self, plug) -> None:
        """Initialize the VeSync switch device."""
        super().__init__(plug)
        self.smartplug = plug

    def update(self) -> None:
        """Update outlet details and energy usage."""
        self.smartplug.update()
        self.smartplug.update_energy()


class VeSyncLightSwitch(VeSyncBaseSwitch, SwitchEntity):
    """Handle representation of VeSync Light Switch."""

    def __init__(self, switch) -> None:
        """Initialize Light Switch device class."""
        super().__init__(switch)
        self.switch = switch


@dataclass
class VeSyncSwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    is_on_fn: Callable[[VeSyncAirBypass], bool]
    # value_fn: Callable[[VeSyncAirBypass], StateType]


@dataclass
class VeSyncSwitchEntityDescription(
    SwitchEntityDescription, VeSyncSwitchEntityDescriptionMixin
):
    """Describe VeSync sensor entity."""

    exists_fn: Callable[[VeSyncAirBypass], bool] = lambda _: True
    update_fn: Callable[[VeSyncAirBypass], None] = lambda _: None
    turn_on_fn: Callable[[VeSyncAirBypass], None] = lambda _: None
    turn_off_fn: Callable[[VeSyncAirBypass], None] = lambda _: None


FAN_SWITCHES: tuple[VeSyncSwitchEntityDescription, ...] = (
    VeSyncSwitchEntityDescription(
        key="display",
        translation_key="display",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:monitor-shimmer",
        is_on_fn=lambda device: device.display_state,
        exists_fn=lambda device: sku_supported(device, DISPLAY_SUPPORTED),
        turn_on_fn=lambda device: device.set_display(True),
        turn_off_fn=lambda device: device.set_display(False),
    ),
    VeSyncSwitchEntityDescription(
        key="light-detection",
        translation_key="light_detection",
        icon="mdi:lightbulb-auto-outline",
        entity_category=EntityCategory.CONFIG,
        force_update=False,
        is_on_fn=lambda device: device.light_detection,
        exists_fn=lambda device: sku_supported(device, LIGHT_MODE_SUPPORTED),
        turn_on_fn=lambda device: device.set_light_detection_on(),
        turn_off_fn=lambda device: device.set_light_detection_off(),
    ),
    VeSyncSwitchEntityDescription(
        key="child-lock",
        translation_key="child_lock",
        icon="mdi:monitor-lock",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.child_lock,
        exists_fn=lambda device: sku_supported(device, CHILD_LOCK_SUPPORTED),
        turn_on_fn=lambda device: device.child_lock_on(),
        turn_off_fn=lambda device: device.child_lock_off(),
    ),
)


class VeSyncFanSwitchEntity(VeSyncBaseEntity, SwitchEntity):
    """Describe VeSync fan switch entity."""

    entity_description: VeSyncSwitchEntityDescription

    def __init__(
        self,
        device: VeSyncAirBypass,
        description: VeSyncSwitchEntityDescription,
    ) -> None:
        """Initialize the VeSync outlet device."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Get current switch state."""
        return self.entity_description.is_on_fn(self.device)

    def update(self) -> None:
        """Run the update function defined for the switch."""
        self.entity_description.update_fn(self.device)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        self.entity_description.turn_on_fn(self.device)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        self.entity_description.turn_off_fn(self.device)
