"""Support for TPLink button entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from kasa import Feature

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TPLinkConfigEntry
from .deprecate import DeprecatedInfo
from .entity import CoordinatedTPLinkFeatureEntity, TPLinkFeatureEntityDescription


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
    first_check = True

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

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


class TPLinkButtonEntity(CoordinatedTPLinkFeatureEntity, ButtonEntity):
    """Representation of a TPLink button entity."""

    entity_description: TPLinkButtonEntityDescription

    async def async_press(self) -> None:
        """Execute action."""
        await self._feature.set_value(True)

    def _async_update_attrs(self) -> bool:
        """No need to update anything."""
        return self.entity_description.available_fn(self._device)
