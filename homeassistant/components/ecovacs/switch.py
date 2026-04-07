"""Ecovacs switch module."""

from dataclasses import dataclass
from typing import Any

from deebot_client.capabilities import CapabilitySetEnable
from deebot_client.device import Device
from deebot_client.events import EnableEvent

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .const import CAMERA_STREAM_STATE_SIGNAL
from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
)
from .util import get_supported_entities


@dataclass(kw_only=True, frozen=True)
class EcovacsSwitchEntityDescription(
    SwitchEntityDescription,
    EcovacsCapabilityEntityDescription[CapabilitySetEnable],
):
    """Ecovacs switch entity description."""


ENTITY_DESCRIPTIONS: tuple[EcovacsSwitchEntityDescription, ...] = (
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.advanced_mode,
        key="advanced_mode",
        translation_key="advanced_mode",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.clean.continuous,
        key="continuous_cleaning",
        translation_key="continuous_cleaning",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.carpet_auto_fan_boost,
        key="carpet_auto_fan_boost",
        translation_key="carpet_auto_fan_boost",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.clean.preference,
        key="clean_preference",
        translation_key="clean_preference",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.true_detect,
        key="true_detect",
        translation_key="true_detect",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.border_switch,
        key="border_switch",
        translation_key="border_switch",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.child_lock,
        key="child_lock",
        translation_key="child_lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.moveup_warning,
        key="move_up_warning",
        translation_key="move_up_warning",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.cross_map_border_warning,
        key="cross_map_border_warning",
        translation_key="cross_map_border_warning",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.safe_protect,
        key="safe_protect",
        translation_key="safe_protect",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    EcovacsSwitchEntityDescription(
        capability_fn=lambda c: c.settings.border_spin,
        key="border_spin",
        translation_key="border_spin",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities: list[EcovacsEntity | CameraStreamSwitch] = get_supported_entities(
        controller, EcovacsSwitchEntity, ENTITY_DESCRIPTIONS
    )
    # Add a camera stream switch for every device (disabled by default)
    entities.extend(
        CameraStreamSwitch(device, config_entry) for device in controller.devices
    )
    if entities:
        async_add_entities(entities)


class EcovacsSwitchEntity(
    EcovacsDescriptionEntity[CapabilitySetEnable],
    SwitchEntity,
):
    """Ecovacs switch entity."""

    entity_description: EcovacsSwitchEntityDescription

    _attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EnableEvent) -> None:
            self._attr_is_on = event.enabled
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._device.execute_command(self._capability.set(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._device.execute_command(self._capability.set(False))


class CameraStreamSwitch(SwitchEntity):
    """Toggle switch that starts/stops the KVS camera stream for an Ecovacs robot.

    State is kept in sync with the camera entity via the dispatcher signal
    CAMERA_STREAM_STATE_SIGNAL, so turning the stream on/off from any source
    (automation, service call, or this switch) is always reflected here.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "camera_stream_switch"
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False

    def __init__(self, device: Device, config_entry: EcovacsConfigEntry) -> None:
        """Initialize."""
        super().__init__()
        self._device = device
        self._config_entry = config_entry
        did = device.device_info["did"]
        self._did = did
        self._attr_unique_id = f"{did}_camera_stream_switch"
        self._is_stream_on: bool = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info (same device as the camera entity)."""
        return DeviceInfo(identifiers={("ecovacs", self._did)})

    @property
    def is_on(self) -> bool:
        """Return True when the stream is active."""
        return self._is_stream_on

    async def async_added_to_hass(self) -> None:
        """Subscribe to camera stream state changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                CAMERA_STREAM_STATE_SIGNAL.format(did=self._did),
                self._on_stream_state_change,
            )
        )

    @callback
    def _on_stream_state_change(self, is_on: bool) -> None:
        """Handle stream state change dispatched by the camera entity."""
        self._is_stream_on = is_on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the camera stream."""
        cam = self._config_entry.runtime_data.get_camera_entity(self._did)
        if cam is not None:
            await cam.async_turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the camera stream."""
        cam = self._config_entry.runtime_data.get_camera_entity(self._did)
        if cam is not None:
            await cam.async_turn_off()
