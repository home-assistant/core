"""Common code for tplink."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any, Concatenate, ParamSpec, TypeVar

from kasa import (
    AuthenticationException,
    Device,
    DeviceType,
    Feature,
    SmartDevice,
    SmartDeviceException,
    TimeoutException,
)

from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import legacy_device_id
from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator

_T = TypeVar("_T", bound="CoordinatedTPLinkEntity")
_P = ParamSpec("_P")


_LOGGER = logging.getLogger(__name__)


def async_refresh_after(
    func: Callable[Concatenate[_T, _P], Awaitable[None]],
) -> Callable[Concatenate[_T, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to raise HA errors and refresh after."""

    async def _async_wrap(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except AuthenticationException as ex:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_authentication",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        except TimeoutException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_timeout",
                translation_placeholders={
                    "func": func.__name__,
                    "exc": str(ex),
                },
            ) from ex
        except SmartDeviceException as ex:
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
        device: SmartDevice,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature = None,
        parent: SmartDevice = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device: SmartDevice = device
        # TODO: clean up this mess.
        # If the entity is based on feature, we use its ID as part of the unique id
        if feature is not None:
            self._attr_unique_id = f"{legacy_device_id(device)}_{feature.id}"
            self._attr_entity_category = self._category_for_feature(feature)
            _LOGGER.warning(
                "Initializing feature-based %s with category %s",
                self._attr_unique_id,
                self._attr_entity_category,
            )

        # Otherwise, if we have entity_description, we use its key
        elif self._attr_unique_id is None and hasattr(self, "entity_description"):
            self._attr_unique_id = (
                f"{legacy_device_id(device)}_{self.entity_description.key}"
            )
            _LOGGER.warning(
                "Got empty feature: %s %s, using entity_description key"
                " as part of the unique id: %s",
                self,
                type(self),
                self._attr_unique_id,
            )

        # Finally, if there's no feature nor description, the entity is main platform (e.g., light or fan)
        else:
            _LOGGER.warning(
                "No unique id nor entity_description given for %s,"
                " unique id based on the device id: %s",
                type(self),
                legacy_device_id(device),
            )
            self._attr_unique_id = legacy_device_id(device)

        self._feature = feature

        self._attr_device_info = DeviceInfo(
            # TODO: find out if connections have any use and/or if it should
            #  still be set for the main device. if set for child devices, all
            #  devices will be presented by a single device
            # connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
            identifiers={(DOMAIN, str(device.device_id))},
            manufacturer="TP-Link",
            model=device.model,
            name=device.alias,
            sw_version=device.hw_info["sw_ver"],
            hw_version=device.hw_info["hw_ver"],
        )

        if parent is not None:
            self._attr_device_info["via_device"] = (DOMAIN, parent.device_id)

    def _category_for_feature(self, feature: Feature):
        match feature.category:
            case Feature.Category.Primary:  # Main controls have no category
                return None
            case Feature.Category.Info:
                return None
            case Feature.Category.Config:
                return EntityCategory.CONFIG
            case Feature.Category.Debug:
                return EntityCategory.DIAGNOSTIC

    @abstractmethod
    @callback
    def _async_update_attrs(self):
        """Implement to update the entity internals."""
        raise NotImplementedError

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            self._async_update_attrs()
            self._attr_available = True
        except Exception as ex:
            _LOGGER.warning(
                "Unable to read data for %s %s: %s",
                self.device,
                self.entity_description,
                ex,
            )
            self._attr_available = False

        super()._handle_coordinator_update()


def _entities_for_device(
    device,
    *,
    feature_type: Feature.Type,
    entity_class: type[CoordinatedTPLinkEntity],
    coordinator: TPLinkDataUpdateCoordinator,
    parent: Device = None,
) -> list[CoordinatedTPLinkEntity]:
    """Return a list of entities to add.

    This filters out unwanted features to avoid creating unnecessary entities
    for device features that are implemented by specialized platforms like light.
    """

    def _filter(dev: Device, feat: Feature):
        if feat.type != feature_type:
            return False

        # We skip primary features for device types that have specialized platforms,
        #  like light for lights.
        ignore_primary_controls_devicetypes = [
            DeviceType.Bulb,
            DeviceType.LightStrip,
            DeviceType.Dimmer,
            DeviceType.Thermostat,
        ]
        if (
            feat.category == Feature.Category.Primary
            and dev.device_type in ignore_primary_controls_devicetypes
        ):
            return False

        return True

    return [
        entity_class(device, coordinator, feat, parent=parent)
        for feat in device.features.values()
        if _filter(device, feat)
    ]


def _entities_for_device_and_its_children(
    device: Device,
    *,
    feature_type: Feature.Type,
    entity_class: type[CoordinatedTPLinkEntity],
    coordinator: TPLinkDataUpdateCoordinator,
) -> list[CoordinatedTPLinkEntity]:
    """Create entities for device and its children.

    This is just a helper that calls *_entities_for_device*.
    """
    entities = []
    if device.children:
        _LOGGER.debug("Initializing device with %s children", len(device.children))
        for child in device.children:
            entities.extend(
                _entities_for_device(
                    child,
                    feature_type=feature_type,
                    entity_class=entity_class,
                    coordinator=coordinator,
                    parent=device,
                )
            )

    entities.extend(
        _entities_for_device(
            device,
            feature_type=feature_type,
            entity_class=entity_class,
            coordinator=coordinator,
        )
    )

    return entities
