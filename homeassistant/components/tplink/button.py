"""Support for TPLink button entities."""

from dataclasses import dataclass
from typing import Final, override

from kasa import Device, Feature, KasaException, Module

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import legacy_device_id
from .coordinator import TPLinkConfigEntry, TPLinkDataUpdateCoordinator
from .deprecate import DeprecatedInfo
from .entity import (
    CoordinatedTPLinkEntity,
    CoordinatedTPLinkFeatureEntity,
    TPLinkFeatureEntityDescription,
    async_refresh_after,
)


@dataclass(frozen=True, kw_only=True)
class TPLinkButtonEntityDescription(
    ButtonEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based button entity description."""


# Coordinator is used to centralize the data updates
# For actions the integration handles locking of concurrent device request
PARALLEL_UPDATES = 0

BUTTON_DESCRIPTIONS: Final = [
    TPLinkButtonEntityDescription(
        key="test_alarm",
        deprecated_info=DeprecatedInfo(
            platform=BUTTON_DOMAIN,
            new_platform=SIREN_DOMAIN,
            breaks_in_ha_version="2025.4.0",
        ),
    ),
    TPLinkButtonEntityDescription(
        key="stop_alarm",
        deprecated_info=DeprecatedInfo(
            platform=BUTTON_DOMAIN,
            new_platform=SIREN_DOMAIN,
            breaks_in_ha_version="2025.4.0",
        ),
    ),
    TPLinkButtonEntityDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
    ),
    TPLinkButtonEntityDescription(
        key="pan_left",
        available_fn=lambda dev: dev.is_on,
    ),
    TPLinkButtonEntityDescription(
        key="pan_right",
        available_fn=lambda dev: dev.is_on,
    ),
    TPLinkButtonEntityDescription(
        key="tilt_up",
        available_fn=lambda dev: dev.is_on,
    ),
    TPLinkButtonEntityDescription(
        key="tilt_down",
        available_fn=lambda dev: dev.is_on,
    ),
    TPLinkButtonEntityDescription(key="pair"),
    TPLinkButtonEntityDescription(key="unpair"),
    TPLinkButtonEntityDescription(
        key="main_brush_reset",
    ),
    TPLinkButtonEntityDescription(
        key="side_brush_reset",
    ),
    TPLinkButtonEntityDescription(
        key="sensor_reset",
    ),
    TPLinkButtonEntityDescription(
        key="filter_reset",
    ),
    TPLinkButtonEntityDescription(
        key="charging_contacts_reset",
    ),
]

BUTTON_DESCRIPTIONS_MAP = {desc.key: desc for desc in BUTTON_DESCRIPTIONS}

PTZ_PRESET_DESCRIPTION = TPLinkButtonEntityDescription(
    key="ptz_preset",
    translation_key="ptz_preset",
    available_fn=lambda dev: dev.is_on,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device
    known_child_device_ids: set[str] = set()
    known_preset_ids: dict[str, set[str]] = {}
    first_check = True

    def _ptz_preset_entities(
        dev: Device, parent: Device | None
    ) -> list[TPLinkPtzPresetButtonEntity]:
        if (pan_tilt := dev.modules.get(Module.PanTilt)) is None:
            return []
        try:
            presets = pan_tilt.presets
        except KasaException:
            # Try again on the next update, don't lose the other cameras
            return []
        known = known_preset_ids.setdefault(dev.device_id, set())
        new_presets = {
            preset_id: name
            for name, preset_id in presets.items()
            if preset_id not in known
        }
        if not new_presets:
            return []
        known.update(new_presets)
        coordinator = (
            parent_coordinator
            if parent is None
            else parent_coordinator.get_child_coordinator(dev, BUTTON_DOMAIN)
        )
        return [
            TPLinkPtzPresetButtonEntity(
                dev,
                coordinator,
                preset_id=preset_id,
                preset_name=name,
                parent=parent,
            )
            for preset_id, name in new_presets.items()
        ]

    def _check_ptz_presets() -> None:
        # A removed child gets its preset buttons again when it is paired again
        for removed_child_id in parent_coordinator.removed_child_device_ids:
            known_preset_ids.pop(removed_child_id, None)
        entities = _ptz_preset_entities(device, None)
        for child in device.children:
            entities.extend(_ptz_preset_entities(child, device))
        if entities:
            async_add_entities(entities)

    def _check_device() -> None:
        entities = CoordinatedTPLinkFeatureEntity.entities_for_device_and_its_children(
            hass=hass,
            device=device,
            coordinator=parent_coordinator,
            feature_type=Feature.Type.Action,
            entity_class=TPLinkButtonEntity,
            descriptions=BUTTON_DESCRIPTIONS_MAP,
            platform_domain=BUTTON_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)
        _check_ptz_presets()

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


class TPLinkButtonEntity(CoordinatedTPLinkFeatureEntity, ButtonEntity):
    """Representation of a TPLink button entity."""

    entity_description: TPLinkButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Execute action."""
        await self._feature.set_value(True)

    @override
    def _async_update_attrs(self) -> bool:
        """No need to update anything."""
        return self.entity_description.available_fn(self._device)


class TPLinkPtzPresetButtonEntity(CoordinatedTPLinkEntity, ButtonEntity):
    """Button that moves the camera to a saved PTZ preset."""

    entity_description: TPLinkButtonEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        preset_id: str,
        preset_name: str,
        parent: Device | None = None,
    ) -> None:
        """Initialize the PTZ preset button."""
        self._preset_id = preset_id
        self._pan_tilt = device.modules[Module.PanTilt]
        super().__init__(device, coordinator, PTZ_PRESET_DESCRIPTION, parent=parent)
        self._attr_translation_placeholders = {"preset_name": preset_name}

    @override
    def _get_unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{legacy_device_id(self._device)}_ptz_preset_{self._preset_id}"

    @async_refresh_after
    @override
    async def async_press(self) -> None:
        """Move the camera to the preset."""
        await self._pan_tilt.goto_preset(self._preset_id)

    @override
    def _async_update_attrs(self) -> bool:
        """Follow preset renames, the button is unavailable when it was removed."""
        preset_names = {
            preset_id: name for name, preset_id in self._pan_tilt.presets.items()
        }
        if (preset_name := preset_names.get(self._preset_id)) is None:
            return False
        if preset_name != self._attr_translation_placeholders["preset_name"]:
            self._attr_translation_placeholders = {"preset_name": preset_name}
            # The entity name is cached, invalidate it to pick up the rename
            self.__dict__.pop("name", None)
        return self.entity_description.available_fn(self._device)
