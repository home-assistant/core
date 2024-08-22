"""Shared Entity definition for UniFi Protect Integration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from functools import partial
import logging
from operator import attrgetter
from typing import TYPE_CHECKING

from uiprotect.data import NVR, Event, ModelType, ProtectAdoptableDeviceModel, StateType

from homeassistant.core import callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import (
    ATTR_EVENT_ID,
    ATTR_EVENT_SCORE,
    DEFAULT_ATTRIBUTION,
    DEFAULT_BRAND,
    DOMAIN,
)
from .data import ProtectData, ProtectDeviceType
from .models import PermRequired, ProtectEntityDescription, ProtectEventMixin

_LOGGER = logging.getLogger(__name__)


@callback
def _async_device_entities(
    data: ProtectData,
    klass: type[BaseProtectEntity],
    model_type: ModelType,
    descs: Sequence[ProtectEntityDescription],
    unadopted_descs: Sequence[ProtectEntityDescription] | None = None,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[BaseProtectEntity]:
    if not descs and not unadopted_descs:
        return []

    entities: list[BaseProtectEntity] = []
    devices = (
        [ufp_device]
        if ufp_device is not None
        else data.get_by_types({model_type}, ignore_unadopted=False)
    )
    auth_user = data.api.bootstrap.auth_user
    for device in devices:
        if TYPE_CHECKING:
            assert isinstance(device, ProtectAdoptableDeviceModel)
        if not device.is_adopted_by_us:
            if unadopted_descs:
                for description in unadopted_descs:
                    entities.append(
                        klass(
                            data,
                            device=device,
                            description=description,
                        )
                    )
                    _LOGGER.debug(
                        "Adding %s entity %s for %s",
                        klass.__name__,
                        description.name,
                        device.display_name,
                    )
            continue

        can_write = device.can_write(auth_user)
        for description in descs:
            if (perms := description.ufp_perm) is not None:
                if perms is PermRequired.WRITE and not can_write:
                    continue
                if perms is PermRequired.NO_WRITE and can_write:
                    continue
                if perms is PermRequired.DELETE and not device.can_delete(auth_user):
                    continue

            if not description.has_required(device):
                continue

            entities.append(
                klass(
                    data,
                    device=device,
                    description=description,
                )
            )
            _LOGGER.debug(
                "Adding %s entity %s for %s",
                klass.__name__,
                description.name,
                device.display_name,
            )

    return entities


_ALL_MODEL_TYPES = (
    ModelType.CAMERA,
    ModelType.LIGHT,
    ModelType.SENSOR,
    ModelType.VIEWPORT,
    ModelType.DOORLOCK,
    ModelType.CHIME,
)


@callback
def _combine_model_descs(
    model_type: ModelType,
    model_descriptions: dict[ModelType, Sequence[ProtectEntityDescription]] | None,
    all_descs: Sequence[ProtectEntityDescription] | None,
) -> list[ProtectEntityDescription]:
    """Combine all the descriptions with descriptions a model type."""
    descs: list[ProtectEntityDescription] = list(all_descs) if all_descs else []
    if model_descriptions and (model_descs := model_descriptions.get(model_type)):
        descs.extend(model_descs)
    return descs


@callback
def async_all_device_entities(
    data: ProtectData,
    klass: type[BaseProtectEntity],
    model_descriptions: dict[ModelType, Sequence[ProtectEntityDescription]]
    | None = None,
    all_descs: Sequence[ProtectEntityDescription] | None = None,
    unadopted_descs: list[ProtectEntityDescription] | None = None,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[BaseProtectEntity]:
    """Generate a list of all the device entities."""
    if ufp_device is None:
        entities: list[BaseProtectEntity] = []
        for model_type in _ALL_MODEL_TYPES:
            descs = _combine_model_descs(model_type, model_descriptions, all_descs)
            entities.extend(
                _async_device_entities(data, klass, model_type, descs, unadopted_descs)
            )
        return entities

    device_model_type = ufp_device.model
    assert device_model_type is not None
    descs = _combine_model_descs(device_model_type, model_descriptions, all_descs)
    return _async_device_entities(
        data, klass, device_model_type, descs, unadopted_descs, ufp_device
    )


class BaseProtectEntity(Entity):
    """Base class for UniFi protect entities."""

    device: ProtectDeviceType

    _attr_should_poll = False
    _attr_attribution = DEFAULT_ATTRIBUTION
    _state_attrs: tuple[str, ...] = ("_attr_available",)
    _attr_has_entity_name = True
    _async_get_ufp_enabled: Callable[[ProtectAdoptableDeviceModel], bool] | None = None

    def __init__(
        self,
        data: ProtectData,
        device: ProtectDeviceType,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.data = data
        self.device = device

        if description is None:
            self._attr_unique_id = self.device.mac
            self._attr_name = None
        else:
            self.entity_description = description
            self._attr_unique_id = f"{self.device.mac}_{description.key}"
            if isinstance(description, ProtectEntityDescription):
                self._async_get_ufp_enabled = description.get_ufp_enabled

        self._async_set_device_info()
        self._state_getters = tuple(
            partial(attrgetter(attr), self) for attr in self._state_attrs
        )

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.data.async_refresh()

    @callback
    def _async_set_device_info(self) -> None:
        """Set device info."""

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        """Update Entity object from Protect device."""
        was_available = self._attr_available
        if last_updated_success := self.data.last_update_success:
            self.device = device

        if device.model is ModelType.NVR:
            available = last_updated_success
        else:
            if TYPE_CHECKING:
                assert isinstance(device, ProtectAdoptableDeviceModel)
            connected = device.state is StateType.CONNECTED or (
                not device.is_adopted_by_us and device.can_adopt
            )
            async_get_ufp_enabled = self._async_get_ufp_enabled
            enabled = not async_get_ufp_enabled or async_get_ufp_enabled(device)
            available = last_updated_success and connected and enabled

        if available != was_available:
            self._attr_available = available

    @callback
    def _async_updated_event(self, device: ProtectDeviceType) -> None:
        """When device is updated from Protect."""
        previous_attrs = [getter() for getter in self._state_getters]
        self._async_update_device_from_protect(device)
        changed = False
        for idx, getter in enumerate(self._state_getters):
            if previous_attrs[idx] != getter():
                changed = True
                break

        if changed:
            if _LOGGER.isEnabledFor(logging.DEBUG):
                device_name = device.name or ""
                if hasattr(self, "entity_description") and self.entity_description.name:
                    device_name += f" {self.entity_description.name}"

                _LOGGER.debug(
                    "Updating state [%s (%s)] %s -> %s",
                    device_name,
                    device.mac,
                    previous_attrs,
                    tuple((getattr(self, attr)) for attr in self._state_attrs),
                )
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.async_subscribe(self.device.mac, self._async_updated_event)
        )
        self._async_update_device_from_protect(self.device)


class ProtectIsOnEntity(BaseProtectEntity):
    """Base class for entities with is_on property."""

    _state_attrs: tuple[str, ...] = ("_attr_available", "_attr_is_on")
    _attr_is_on: bool | None
    entity_description: ProtectEntityDescription

    def _async_update_device_from_protect(
        self, device: ProtectAdoptableDeviceModel | NVR
    ) -> None:
        super()._async_update_device_from_protect(device)
        was_on = self._attr_is_on
        if was_on != (is_on := self.entity_description.get_ufp_value(device) is True):
            self._attr_is_on = is_on


class ProtectDeviceEntity(BaseProtectEntity):
    """Base class for UniFi protect entities."""

    @callback
    def _async_set_device_info(self) -> None:
        self._attr_device_info = DeviceInfo(
            name=self.device.display_name,
            manufacturer=DEFAULT_BRAND,
            model=self.device.type,
            via_device=(DOMAIN, self.data.api.bootstrap.nvr.mac),
            sw_version=self.device.firmware_version,
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            configuration_url=self.device.protect_url,
        )


class ProtectNVREntity(BaseProtectEntity):
    """Base class for unifi protect entities."""

    device: NVR

    @callback
    def _async_set_device_info(self) -> None:
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, self.device.mac)},
            manufacturer=DEFAULT_BRAND,
            name=self.device.display_name,
            model=self.device.type,
            sw_version=str(self.device.version),
            configuration_url=self.device.api.base_url,
        )


class EventEntityMixin(ProtectDeviceEntity):
    """Adds motion event attributes to sensor."""

    entity_description: ProtectEventMixin
    _unrecorded_attributes = frozenset({ATTR_EVENT_ID, ATTR_EVENT_SCORE})
    _event: Event | None = None
    _event_end: datetime | None = None

    @callback
    def _set_event_done(self) -> None:
        """Clear the event and state."""

    @callback
    def _set_event_attrs(self, event: Event) -> None:
        """Set event attrs."""
        self._attr_extra_state_attributes = {
            ATTR_EVENT_ID: event.id,
            ATTR_EVENT_SCORE: event.score,
        }

    @callback
    def _async_event_with_immediate_end(self) -> None:
        # If the event is so short that the detection is received
        # in the same message as the end of the event we need to write
        # state and than clear the event and write state again.
        self.async_write_ha_state()
        self._set_event_done()
        self.async_write_ha_state()

    @callback
    def _event_already_ended(
        self, prev_event: Event | None, prev_event_end: datetime | None
    ) -> bool:
        """Determine if the event has already ended.

        The event_end time is passed because the prev_event and event object
        may be the same object, and the uiprotect code will mutate the
        event object so we need to check the datetime object that was
        saved from the last time the entity was updated.
        """
        return bool(
            (event := self._event)
            and event.end
            and prev_event
            and prev_event_end
            and prev_event.id == event.id
        )
