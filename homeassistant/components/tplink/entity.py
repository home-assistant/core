"""Common code for tplink."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any, Concatenate, TypedDict, Unpack

from kasa import (
    AuthenticationError,
    Device,
    DeviceType,
    Feature,
    KasaException,
    TimeoutError,
)

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import legacy_device_id
from .const import DOMAIN, PRIMARY_STATE_ID
from .coordinator import TPLinkDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# Mapping from upstream category to homeassistant category
FEATURE_CATEGORY_TO_ENTITY_CATEGORY = {
    Feature.Category.Config: EntityCategory.CONFIG,
    Feature.Category.Info: EntityCategory.DIAGNOSTIC,
    Feature.Category.Debug: EntityCategory.DIAGNOSTIC,
}

# Skips creating entities for primary features supported by a specialized platform.
# For example, we do not need a separate "state" switch for light bulbs.
DEVICETYPES_WITH_SPECIALIZED_PLATFORMS = {
    DeviceType.Bulb,
    DeviceType.LightStrip,
    DeviceType.Dimmer,
}


class EntityDescriptionExtras(TypedDict, total=False):
    """Extra kwargs that can be provided to entity descriptions."""

    entity_registry_enabled_default: bool


def async_refresh_after[_T: CoordinatedTPLinkEntity, **_P](
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to raise HA errors and refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except AuthenticationError as ex:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_authentication",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        except TimeoutError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_timeout",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        except KasaException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_error",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        await self.coordinator.async_request_refresh()

    return _async_wrap


class CoordinatedTPLinkEntity(CoordinatorEntity[TPLinkDataUpdateCoordinator], ABC):
    """Common base class for all coordinated tplink entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature | None = None,
        parent: Device | None = None,
        unique_id: str | None = None,
        add_to_parent: bool = False,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device: Device = device
        self._feature = feature

        registry_device = device
        name = device.alias
        if parent and parent.device_type != Device.Type.Hub:
            if add_to_parent:
                # Entity can be added to parent if add_to_parent parameter and not a hub
                # Useful to assign primary controls to the parent for user experience.
                registry_device = parent
                name = registry_device.alias
                self._attr_name = device.alias
            else:
                # Prefix the device name with the parent name unless it is a hub attached device.
                # Sensible default for child devices like strip plugs or the ks240 where the child
                # alias makes more sense in the context of the parent.
                # i.e. Hall Ceiling Fan & Bedroom Ceiling Fan; Child device aliases will be Ceiling Fan
                # and Dimmer Switch for both so should be distinguished by the parent name.
                name = f"{parent.alias} {device.alias}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(registry_device.device_id))},
            manufacturer="TP-Link",
            model=registry_device.model,
            name=name,
            sw_version=registry_device.hw_info["sw_ver"],
            hw_version=registry_device.hw_info["hw_ver"],
        )

        if parent is not None and parent != registry_device:
            self._attr_device_info["via_device"] = (DOMAIN, parent.device_id)
        else:
            self._attr_device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, device.mac)
            }

        # The rest of the initialization takes care of setting a proper unique_id
        # This is transitional and will become cleaner as future platforms get converted.

        # Specialized platforms define their own unique ids.
        if unique_id is not None:
            self._attr_unique_id = unique_id
            return

        # If no unique id is defined and we have no feature, it's a bug.
        if feature is None:
            raise HomeAssistantError(
                "Entity is not feature-based nor does define unique_id"
            )

        self._attr_entity_category = self._category_for_feature(feature)

        # Special handling for primary state attribute (backwards compat for the main switch).
        if feature.id == PRIMARY_STATE_ID:
            self._attr_unique_id = legacy_device_id(device)
        else:
            self._attr_unique_id = f"{legacy_device_id(device)}_{feature.id}"
            _LOGGER.debug(
                "Initializing feature-based %s with category %s",
                self._attr_unique_id,
                self._attr_entity_category,
            )

    def _category_for_feature(self, feature: Feature) -> EntityCategory | None:
        """Return entity category for a feature."""
        # Main controls have no category
        if feature.category is Feature.Category.Primary:
            return None

        if (
            entity_category := FEATURE_CATEGORY_TO_ENTITY_CATEGORY.get(feature.category)
        ) is None:
            _LOGGER.error(
                "Unhandled category %s, fallback to DIAGNOSTIC", feature.category
            )
            entity_category = EntityCategory.DIAGNOSTIC

        return entity_category

    @abstractmethod
    @callback
    def _async_update_attrs(self) -> None:
        """Platforms implement this to update the entity internals."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._async_update_attrs()
        except Exception as ex:  # noqa: BLE001
            if self._attr_available:
                _LOGGER.warning(
                    "Unable to read data for %s %s: %s",
                    self.device,
                    self.entity_description,
                    ex,
                )
            self._attr_available = False

        self._attr_available = True
        super()._handle_coordinator_update()


def _entities_for_device[_E: CoordinatedTPLinkEntity](
    device: Device,
    coordinator: TPLinkDataUpdateCoordinator,
    *,
    feature_type: Feature.Type,
    entity_class: type[_E],
    parent: Device | None = None,
) -> list[_E]:
    """Return a list of entities to add.

    This filters out unwanted features to avoid creating unnecessary entities
    for device features that are implemented by specialized platforms like light.
    """
    return [
        entity_class(
            device,
            coordinator,
            feature=feat,
            parent=parent,
            add_to_parent=feat.category == Feature.Category.Primary,
        )
        for feat in device.features.values()
        if feat.type == feature_type
        and (
            feat.category != Feature.Category.Primary
            or device.device_type not in DEVICETYPES_WITH_SPECIALIZED_PLATFORMS
        )
    ]


def _entities_for_device_and_its_children[_E: CoordinatedTPLinkEntity](
    device: Device,
    coordinator: TPLinkDataUpdateCoordinator,
    *,
    feature_type: Feature.Type,
    entity_class: type[_E],
) -> list[_E]:
    """Create entities for device and its children.

    This is a helper that calls *_entities_for_device* for the device and its children.
    """
    entities: list[_E] = []
    if device.children:
        _LOGGER.debug("Initializing device with %s children", len(device.children))
        for child in device.children:
            entities.extend(
                _entities_for_device(
                    child,
                    coordinator=coordinator,
                    feature_type=feature_type,
                    entity_class=entity_class,
                    parent=device,
                )
            )

    entities.extend(
        _entities_for_device(
            device,
            coordinator=coordinator,
            feature_type=feature_type,
            entity_class=entity_class,
        )
    )

    return entities


def _description_for_feature[_D: EntityDescription](
    desc_cls: type[_D], feature: Feature, **kwargs: Unpack[EntityDescriptionExtras]
) -> _D:
    """Return description object for the given feature.

    This is responsible for setting the common parameters & deciding based on feature id
    which additional parameters are passed.
    """

    # Disable all debug features that are not explicitly enabled.
    if "entity_registry_enabled_default" not in kwargs:
        kwargs["entity_registry_enabled_default"] = (
            feature.category is not Feature.Category.Debug
        )

    return desc_cls(
        key=feature.id,
        translation_key=feature.id,
        name=feature.name,
        **kwargs,
    )
