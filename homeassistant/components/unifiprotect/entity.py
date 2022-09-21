"""Shared Entity definition for UniFi Protect Integration."""
from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any

from pyunifiprotect.data import (
    NVR,
    Camera,
    Chime,
    Doorlock,
    Event,
    Light,
    ModelType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
    Sensor,
    StateType,
    Viewer,
)

from homeassistant.core import callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import ATTR_EVENT_SCORE, DEFAULT_ATTRIBUTION, DEFAULT_BRAND, DOMAIN
from .data import ProtectData
from .models import PermRequired, ProtectRequiredKeysMixin
from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)


@callback
def _async_device_entities(
    data: ProtectData,
    klass: type[ProtectDeviceEntity],
    model_type: ModelType,
    descs: Sequence[ProtectRequiredKeysMixin],
    unadopted_descs: Sequence[ProtectRequiredKeysMixin],
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[ProtectDeviceEntity]:
    if not descs and not unadopted_descs:
        return []

    entities: list[ProtectDeviceEntity] = []
    devices = (
        [ufp_device]
        if ufp_device is not None
        else data.get_by_types({model_type}, ignore_unadopted=False)
    )
    for device in devices:
        assert isinstance(device, (Camera, Light, Sensor, Viewer, Doorlock, Chime))
        if not device.is_adopted_by_us:
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

        can_write = device.can_write(data.api.bootstrap.auth_user)
        for description in descs:
            if description.ufp_perm is not None:
                if description.ufp_perm == PermRequired.WRITE and not can_write:
                    continue
                if description.ufp_perm == PermRequired.NO_WRITE and can_write:
                    continue
                if (
                    description.ufp_perm == PermRequired.DELETE
                    and not device.can_delete(data.api.bootstrap.auth_user)
                ):
                    continue

            if description.ufp_required_field:
                required_field = get_nested_attr(device, description.ufp_required_field)
                if not required_field:
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


@callback
def async_all_device_entities(
    data: ProtectData,
    klass: type[ProtectDeviceEntity],
    camera_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    light_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    sense_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    viewer_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    lock_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    chime_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    all_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    unadopted_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[ProtectDeviceEntity]:
    """Generate a list of all the device entities."""
    all_descs = list(all_descs or [])
    unadopted_descs = list(unadopted_descs or [])
    camera_descs = list(camera_descs or []) + all_descs
    light_descs = list(light_descs or []) + all_descs
    sense_descs = list(sense_descs or []) + all_descs
    viewer_descs = list(viewer_descs or []) + all_descs
    lock_descs = list(lock_descs or []) + all_descs
    chime_descs = list(chime_descs or []) + all_descs

    if ufp_device is None:
        return (
            _async_device_entities(
                data, klass, ModelType.CAMERA, camera_descs, unadopted_descs
            )
            + _async_device_entities(
                data, klass, ModelType.LIGHT, light_descs, unadopted_descs
            )
            + _async_device_entities(
                data, klass, ModelType.SENSOR, sense_descs, unadopted_descs
            )
            + _async_device_entities(
                data, klass, ModelType.VIEWPORT, viewer_descs, unadopted_descs
            )
            + _async_device_entities(
                data, klass, ModelType.DOORLOCK, lock_descs, unadopted_descs
            )
            + _async_device_entities(
                data, klass, ModelType.CHIME, chime_descs, unadopted_descs
            )
        )

    descs = []
    if ufp_device.model == ModelType.CAMERA:
        descs = camera_descs
    elif ufp_device.model == ModelType.LIGHT:
        descs = light_descs
    elif ufp_device.model == ModelType.SENSOR:
        descs = sense_descs
    elif ufp_device.model == ModelType.VIEWPORT:
        descs = viewer_descs
    elif ufp_device.model == ModelType.DOORLOCK:
        descs = lock_descs
    elif ufp_device.model == ModelType.CHIME:
        descs = chime_descs

    if not descs and not unadopted_descs or ufp_device.model is None:
        return []
    return _async_device_entities(
        data, klass, ufp_device.model, descs, unadopted_descs, ufp_device
    )


class ProtectDeviceEntity(Entity):
    """Base class for UniFi protect entities."""

    device: ProtectAdoptableDeviceModel

    _attr_should_poll = False

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.data: ProtectData = data
        self.device = device

        if description is None:
            self._attr_unique_id = f"{self.device.mac}"
            self._attr_name = f"{self.device.display_name}"
        else:
            self.entity_description = description
            self._attr_unique_id = f"{self.device.mac}_{description.key}"
            name = description.name or ""
            self._attr_name = f"{self.device.display_name} {name.title()}"

        self._attr_attribution = DEFAULT_ATTRIBUTION
        self._async_set_device_info()
        self._async_update_device_from_protect(device)

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.data.async_refresh()

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

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        """Update Entity object from Protect device."""
        if self.data.last_update_success:
            assert isinstance(device, ProtectAdoptableDeviceModel)
            self.device = device

        is_connected = self.data.last_update_success and (
            self.device.state == StateType.CONNECTED
            or (not self.device.is_adopted_by_us and self.device.can_adopt)
        )
        if (
            hasattr(self, "entity_description")
            and self.entity_description is not None
            and hasattr(self.entity_description, "get_ufp_enabled")
        ):
            assert isinstance(self.entity_description, ProtectRequiredKeysMixin)
            is_connected = is_connected and self.entity_description.get_ufp_enabled(
                self.device
            )
        self._attr_available = is_connected

    @callback
    def _async_updated_event(self, device: ProtectModelWithId) -> None:
        """Call back for incoming data."""
        self._async_update_device_from_protect(device)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.async_subscribe_device_id(
                self.device.mac, self._async_updated_event
            )
        )


class ProtectNVREntity(ProtectDeviceEntity):
    """Base class for unifi protect entities."""

    # separate subclass on purpose
    device: NVR  # type: ignore[assignment]

    def __init__(
        self,
        entry: ProtectData,
        device: NVR,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry, device, description)  # type: ignore[arg-type]

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

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        if self.data.last_update_success:
            self.device = self.data.api.bootstrap.nvr

        self._attr_available = self.data.last_update_success


class EventThumbnailMixin(ProtectDeviceEntity):
    """Adds motion event attributes to sensor."""

    def __init__(self, *args: Any, **kwarg: Any) -> None:
        """Init an sensor that has event thumbnails."""
        super().__init__(*args, **kwarg)
        self._event: Event | None = None

    @callback
    def _async_get_event(self) -> Event | None:
        """Get event from Protect device.

        To be overridden by child classes.
        """
        raise NotImplementedError()

    @callback
    def _async_thumbnail_extra_attrs(self) -> dict[str, Any]:
        # Camera motion sensors with object detection
        attrs: dict[str, Any] = {
            ATTR_EVENT_SCORE: 0,
        }

        if self._event is None:
            return attrs

        attrs[ATTR_EVENT_SCORE] = self._event.score
        return attrs

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        self._event = self._async_get_event()

        attrs = self.extra_state_attributes or {}
        self._attr_extra_state_attributes = {
            **attrs,
            **self._async_thumbnail_extra_attrs(),
        }
