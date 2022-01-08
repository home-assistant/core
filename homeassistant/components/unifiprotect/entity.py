"""Shared Entity definition for UniFi Protect Integration."""
from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from datetime import datetime, timedelta
import hashlib
import logging
from random import SystemRandom
from typing import Any, Final
from urllib.parse import urlencode

from pyunifiprotect.data import (
    Camera,
    Event,
    Light,
    ModelType,
    ProtectAdoptableDeviceModel,
    Sensor,
    StateType,
    Viewer,
)
from pyunifiprotect.data.nvr import NVR

from homeassistant.core import callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import (
    ATTR_EVENT_SCORE,
    ATTR_EVENT_THUMB,
    DEFAULT_ATTRIBUTION,
    DEFAULT_BRAND,
    DOMAIN,
)
from .data import ProtectData
from .models import ProtectRequiredKeysMixin
from .utils import get_nested_attr
from .views import ThumbnailProxyView

EVENT_UPDATE_TOKENS = "unifiprotect_update_tokens"
TOKEN_CHANGE_INTERVAL: Final = timedelta(minutes=1)
_RND: Final = SystemRandom()
_LOGGER = logging.getLogger(__name__)


@callback
def _async_device_entities(
    data: ProtectData,
    klass: type[ProtectDeviceEntity],
    model_type: ModelType,
    descs: Sequence[ProtectRequiredKeysMixin],
) -> list[ProtectDeviceEntity]:
    if len(descs) == 0:
        return []

    entities: list[ProtectDeviceEntity] = []
    for device in data.get_by_types({model_type}):
        assert isinstance(device, (Camera, Light, Sensor, Viewer))
        for description in descs:
            assert isinstance(description, EntityDescription)
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
                device.name,
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
    all_descs: Sequence[ProtectRequiredKeysMixin] | None = None,
) -> list[ProtectDeviceEntity]:
    """Generate a list of all the device entities."""
    all_descs = list(all_descs or [])
    camera_descs = list(camera_descs or []) + all_descs
    light_descs = list(light_descs or []) + all_descs
    sense_descs = list(sense_descs or []) + all_descs
    viewer_descs = list(viewer_descs or []) + all_descs

    return (
        _async_device_entities(data, klass, ModelType.CAMERA, camera_descs)
        + _async_device_entities(data, klass, ModelType.LIGHT, light_descs)
        + _async_device_entities(data, klass, ModelType.SENSOR, sense_descs)
        + _async_device_entities(data, klass, ModelType.VIEWPORT, viewer_descs)
    )


class ProtectDeviceEntity(Entity):
    """Base class for UniFi protect entities."""

    _attr_should_poll = False

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel | None = None,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.data: ProtectData = data

        if device and not hasattr(self, "device"):
            self.device: ProtectAdoptableDeviceModel = device

        if description and not hasattr(self, "entity_description"):
            self.entity_description = description
        elif hasattr(self, "entity_description"):
            description = self.entity_description

        if description is None:
            self._attr_unique_id = f"{self.device.id}"
            self._attr_name = f"{self.device.name}"
        else:
            self._attr_unique_id = f"{self.device.id}_{description.key}"
            name = description.name or ""
            self._attr_name = f"{self.device.name} {name.title()}"

        self._attr_attribution = DEFAULT_ATTRIBUTION
        self._async_set_device_info()
        self._async_update_device_from_protect()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.data.async_refresh()

    @callback
    def _async_set_device_info(self) -> None:
        self._attr_device_info = DeviceInfo(
            name=self.device.name,
            manufacturer=DEFAULT_BRAND,
            model=self.device.type,
            via_device=(DOMAIN, self.data.api.bootstrap.nvr.mac),
            sw_version=self.device.firmware_version,
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            configuration_url=self.device.protect_url,
        )

    @callback
    def _async_update_device_from_protect(self) -> None:
        """Update Entity object from Protect device."""
        if self.data.last_update_success:
            assert self.device.model
            devices = getattr(self.data.api.bootstrap, f"{self.device.model.value}s")
            self.device = devices[self.device.id]

        self._attr_available = (
            self.data.last_update_success and self.device.state == StateType.CONNECTED
        )

    @callback
    def _async_updated_event(self) -> None:
        """Call back for incoming data."""
        self._async_update_device_from_protect()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.async_subscribe_device_id(
                self.device.id, self._async_updated_event
            )
        )


class ProtectNVREntity(ProtectDeviceEntity):
    """Base class for unifi protect entities."""

    def __init__(
        self,
        entry: ProtectData,
        device: NVR,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        # ProtectNVREntity is intentionally a separate base class
        self.device: NVR = device  # type: ignore
        super().__init__(entry, description=description)

    @callback
    def _async_set_device_info(self) -> None:
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, self.device.mac)},
            manufacturer=DEFAULT_BRAND,
            name=self.device.name,
            model=self.device.type,
            sw_version=str(self.device.version),
            configuration_url=self.device.api.base_url,
        )

    @callback
    def _async_update_device_from_protect(self) -> None:
        if self.data.last_update_success:
            self.device = self.data.api.bootstrap.nvr

        self._attr_available = self.data.last_update_success


class AccessTokenMixin(Entity):
    """Adds access_token attribute and provides access tokens for use for anonymous views."""

    @property
    def access_tokens(self) -> deque[str]:
        """Get valid access_tokens for current entity."""
        assert isinstance(self, ProtectDeviceEntity)
        return self.data.async_get_or_create_access_tokens(self.entity_id)

    @callback
    def _async_update_and_write_token(self, now: datetime) -> None:
        _LOGGER.debug("Updating access tokens for %s", self.entity_id)
        self.async_update_token()
        self.async_write_ha_state()

    @callback
    def async_update_token(self) -> None:
        """Update the used token."""
        self.access_tokens.append(
            hashlib.sha256(_RND.getrandbits(256).to_bytes(32, "little")).hexdigest()
        )

    @callback
    def async_cleanup_tokens(self) -> None:
        """Clean up any remaining tokens on removal."""
        assert isinstance(self, ProtectDeviceEntity)
        if self.entity_id in self.data.access_tokens:
            del self.data.access_tokens[self.entity_id]

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        Injects callbacks to update access tokens automatically
        """
        await super().async_added_to_hass()

        self.async_update_token()
        self.async_on_remove(
            self.hass.helpers.event.async_track_time_interval(
                self._async_update_and_write_token, TOKEN_CHANGE_INTERVAL
            )
        )
        self.async_on_remove(self.async_cleanup_tokens)


class EventThumbnailMixin(AccessTokenMixin):
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
            ATTR_EVENT_THUMB: None,
        }

        if self._event is None:
            return attrs

        attrs[ATTR_EVENT_SCORE] = self._event.score
        if len(self.access_tokens) > 0:
            params = urlencode(
                {"entity_id": self.entity_id, "token": self.access_tokens[-1]}
            )
            attrs[ATTR_EVENT_THUMB] = (
                ThumbnailProxyView.url.format(event_id=self._event.id) + f"?{params}"
            )

        return attrs

    @callback
    def _async_update_device_from_protect(self) -> None:
        assert isinstance(self, ProtectDeviceEntity)
        super()._async_update_device_from_protect()  # type: ignore
        self._event = self._async_get_event()

        attrs = self.extra_state_attributes or {}
        self._attr_extra_state_attributes = {
            **attrs,
            **self._async_thumbnail_extra_attrs(),
        }
