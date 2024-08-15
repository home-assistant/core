"""Common code for tplink."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from dataclasses import dataclass, replace
import logging
from typing import Any, Concatenate

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
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_device_name, legacy_device_id
from .const import (
    ATTR_CURRENT_A,
    ATTR_CURRENT_POWER_W,
    ATTR_TODAY_ENERGY_KWH,
    ATTR_TOTAL_ENERGY_KWH,
    DOMAIN,
    PRIMARY_STATE_ID,
)
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
    DeviceType.Fan,
    DeviceType.Thermostat,
}

# Primary features to always include even when the device type has its own platform
FEATURES_ALLOW_LIST = {
    # lights have current_consumption and a specialized platform
    "current_consumption"
}


# Features excluded due to future platform additions
EXCLUDED_FEATURES = {
    # update
    "current_firmware_version",
    "available_firmware_version",
}


LEGACY_KEY_MAPPING = {
    "current": ATTR_CURRENT_A,
    "current_consumption": ATTR_CURRENT_POWER_W,
    "consumption_today": ATTR_TODAY_ENERGY_KWH,
    "consumption_total": ATTR_TOTAL_ENERGY_KWH,
}


@dataclass(frozen=True, kw_only=True)
class TPLinkFeatureEntityDescription(EntityDescription):
    """Base class for a TPLink feature based entity description."""


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
    _device: Device

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature | None = None,
        parent: Device | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device: Device = device
        self._feature = feature

        registry_device = device
        device_name = get_device_name(device, parent=parent)
        if parent and parent.device_type is not Device.Type.Hub:
            if not feature or feature.id == PRIMARY_STATE_ID:
                # Entity will be added to parent if not a hub and no feature
                # parameter (i.e. core platform like Light, Fan) or the feature
                # is the primary state
                registry_device = parent
                device_name = get_device_name(registry_device)
            else:
                # Prefix the device name with the parent name unless it is a
                # hub attached device. Sensible default for child devices like
                # strip plugs or the ks240 where the child alias makes more
                # sense in the context of the parent. i.e. Hall Ceiling Fan &
                # Bedroom Ceiling Fan; Child device aliases will be Ceiling Fan
                # and Dimmer Switch for both so should be distinguished by the
                # parent name.
                device_name = f"{get_device_name(parent)} {get_device_name(device, parent=parent)}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(registry_device.device_id))},
            manufacturer="TP-Link",
            model=registry_device.model,
            name=device_name,
            sw_version=registry_device.hw_info["sw_ver"],
            hw_version=registry_device.hw_info["hw_ver"],
        )

        if (
            parent is not None
            and parent != registry_device
            and parent.device_type is not Device.Type.WallSwitch
        ):
            self._attr_device_info["via_device"] = (DOMAIN, parent.device_id)
        else:
            self._attr_device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, device.mac)
            }

        self._attr_unique_id = self._get_unique_id()

        self._async_call_update_attrs()

    def _get_unique_id(self) -> str:
        """Return unique ID for the entity."""
        return legacy_device_id(self._device)

    @abstractmethod
    @callback
    def _async_update_attrs(self) -> None:
        """Platforms implement this to update the entity internals."""
        raise NotImplementedError

    @callback
    def _async_call_update_attrs(self) -> None:
        """Call update_attrs and make entity unavailable on errors."""
        try:
            self._async_update_attrs()
        except Exception as ex:  # noqa: BLE001
            if self._attr_available:
                _LOGGER.warning(
                    "Unable to read data for %s %s: %s",
                    self._device,
                    self.entity_id,
                    ex,
                )
            self._attr_available = False
        else:
            self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_call_update_attrs()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._attr_available


class CoordinatedTPLinkFeatureEntity(CoordinatedTPLinkEntity, ABC):
    """Common base class for all coordinated tplink feature entities."""

    entity_description: TPLinkFeatureEntityDescription
    _feature: Feature

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature,
        description: TPLinkFeatureEntityDescription,
        parent: Device | None = None,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(device, coordinator, parent=parent, feature=feature)

    def _get_unique_id(self) -> str:
        """Return unique ID for the entity."""
        key = self.entity_description.key
        # The unique id for the state feature in the switch platform is the
        # device_id
        if key == PRIMARY_STATE_ID:
            return legacy_device_id(self._device)

        # Historically the legacy device emeter attributes which are now
        # replaced with features used slightly different keys. This ensures
        # that those entities are not orphaned. Returns the mapped key or the
        # provided key if not mapped.
        key = LEGACY_KEY_MAPPING.get(key, key)
        return f"{legacy_device_id(self._device)}_{key}"

    @classmethod
    def _category_for_feature(cls, feature: Feature | None) -> EntityCategory | None:
        """Return entity category for a feature."""
        # Main controls have no category
        if feature is None or feature.category is Feature.Category.Primary:
            return None

        if (
            entity_category := FEATURE_CATEGORY_TO_ENTITY_CATEGORY.get(feature.category)
        ) is None:
            _LOGGER.error(
                "Unhandled category %s, fallback to DIAGNOSTIC", feature.category
            )
            entity_category = EntityCategory.DIAGNOSTIC

        return entity_category

    @classmethod
    def _description_for_feature[_D: EntityDescription](
        cls,
        feature: Feature,
        descriptions: Mapping[str, _D],
        *,
        device: Device,
        parent: Device | None = None,
    ) -> _D | None:
        """Return description object for the given feature.

        This is responsible for setting the common parameters & deciding
        based on feature id which additional parameters are passed.
        """

        if descriptions and (desc := descriptions.get(feature.id)):
            translation_key: str | None = feature.id
            # HA logic is to name entities based on the following logic:
            # _attr_name > translation.name > description.name
            # > device_class (if base platform supports).
            name: str | None | UndefinedType = UNDEFINED

            # The state feature gets the device name or the child device
            # name if it's a child device
            if feature.id == PRIMARY_STATE_ID:
                translation_key = None
                # if None will use device name
                name = get_device_name(device, parent=parent) if parent else None

            return replace(
                desc,
                translation_key=translation_key,
                name=name,  # if undefined will use translation key
                entity_category=cls._category_for_feature(feature),
                # enabled_default can be overridden to False in the description
                entity_registry_enabled_default=feature.category
                is not Feature.Category.Debug
                and desc.entity_registry_enabled_default,
            )

        _LOGGER.info(
            "Device feature: %s (%s) needs an entity description defined in HA",
            feature.name,
            feature.id,
        )
        return None

    @classmethod
    def _entities_for_device[
        _E: CoordinatedTPLinkFeatureEntity,
        _D: TPLinkFeatureEntityDescription,
    ](
        cls,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature_type: Feature.Type,
        entity_class: type[_E],
        descriptions: Mapping[str, _D],
        parent: Device | None = None,
    ) -> list[_E]:
        """Return a list of entities to add.

        This filters out unwanted features to avoid creating unnecessary entities
        for device features that are implemented by specialized platforms like light.
        """
        entities: list[_E] = [
            entity_class(
                device,
                coordinator,
                feature=feat,
                description=desc,
                parent=parent,
            )
            for feat in device.features.values()
            if feat.type == feature_type
            and feat.id not in EXCLUDED_FEATURES
            and (
                feat.category is not Feature.Category.Primary
                or device.device_type not in DEVICETYPES_WITH_SPECIALIZED_PLATFORMS
                or feat.id in FEATURES_ALLOW_LIST
            )
            and (
                desc := cls._description_for_feature(
                    feat, descriptions, device=device, parent=parent
                )
            )
        ]
        return entities

    @classmethod
    def entities_for_device_and_its_children[
        _E: CoordinatedTPLinkFeatureEntity,
        _D: TPLinkFeatureEntityDescription,
    ](
        cls,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature_type: Feature.Type,
        entity_class: type[_E],
        descriptions: Mapping[str, _D],
        child_coordinators: list[TPLinkDataUpdateCoordinator] | None = None,
    ) -> list[_E]:
        """Create entities for device and its children.

        This is a helper that calls *_entities_for_device* for the device and its children.
        """
        entities: list[_E] = []
        # Add parent entities before children so via_device id works.
        entities.extend(
            cls._entities_for_device(
                device,
                coordinator=coordinator,
                feature_type=feature_type,
                entity_class=entity_class,
                descriptions=descriptions,
            )
        )
        if device.children:
            _LOGGER.debug("Initializing device with %s children", len(device.children))
            for idx, child in enumerate(device.children):
                # HS300 does not like too many concurrent requests and its
                # emeter data requires a request for each socket, so we receive
                # separate coordinators.
                if child_coordinators:
                    child_coordinator = child_coordinators[idx]
                else:
                    child_coordinator = coordinator
                entities.extend(
                    cls._entities_for_device(
                        child,
                        coordinator=child_coordinator,
                        feature_type=feature_type,
                        entity_class=entity_class,
                        descriptions=descriptions,
                        parent=device,
                    )
                )

        return entities
