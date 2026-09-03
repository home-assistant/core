"""Shared Entity definition for UniFi Protect Integration."""

from collections.abc import Callable, Coroutine, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import partial
import logging
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast, override

from uiprotect import (
    get_nested_attr_as_bool,
    make_enabled_getter,
    make_required_getter,
    make_value_getter,
)
from uiprotect.data import (
    NVR,
    Camera,
    DeviceState,
    Event,
    ModelType,
    ProtectAdoptableDeviceModel,
    PublicDeviceModel,
    SmartDetectObjectType,
    StateType,
)
from uiprotect.data.public_devices import (
    PublicCamera,
    PublicSensor,
    SensorFeatureCapability,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import (
    ATTR_EVENT_ID,
    ATTR_EVENT_SCORE,
    ATTR_SMART_DETECT_TYPES,
    DEFAULT_ATTRIBUTION,
    DEFAULT_BRAND,
    DOMAIN,
)
from .data import ProtectData, ProtectDeviceType

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=ProtectAdoptableDeviceModel | NVR)


class PermRequired(int, Enum):
    """Type of permission level required for entity."""

    NO_WRITE = 1
    WRITE = 2
    DELETE = 3


@callback
def _async_capability_supported(
    public: PublicDeviceModel | None,
    private: ProtectAdoptableDeviceModel | None,
    description: ProtectEntityDescription,
) -> bool:
    """Whether the device advertises the description's required capability.

    Smart-detect capabilities are answered by the master object (the private
    camera in hybrid, the public one otherwise). Sensor capabilities come from
    the public capability map; without one every description is created.
    """
    if (capability := description.ufp_capability) is None:
        return True
    if isinstance(capability, SmartDetectObjectType):
        camera = cast(
            "Camera | PublicCamera", private if private is not None else public
        )
        return camera.can_detect(capability)
    if not isinstance(public, PublicSensor) or not public.has_feature_flags:
        return True
    return public.supports(capability)


@callback
def async_remove_unsupported_sense_entities(
    hass: HomeAssistant,
    platform: Platform,
    data: ProtectData,
    descs: Sequence[ProtectEntityDescription],
) -> None:
    """Remove registry entries for sense entities the device cannot support.

    Only acts when a public capability map is present (newer firmware); a console
    upgrade then drops the never-functional entities created before the map existed.
    """
    entity_registry = er.async_get(hass)
    is_public_only = data.api.is_public_only
    for public, private in data.get_public_devices(ModelType.SENSOR):
        if private is not None:
            mac = private.mac
        elif is_public_only and public is not None:
            mac = public.mac
        else:
            # Hybrid: not enumerated until the private fill arrives.
            continue
        for description in descs:
            if description.ufp_capability is None or _async_capability_supported(
                public, private, description
            ):
                continue
            if entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, f"{mac}_{description.key}"
            ):
                entity_registry.async_remove(entity_id)


@callback
def _async_public_only_entities(
    data: ProtectData,
    klass: type[BaseProtectEntity],
    public: PublicDeviceModel,
    descs: Sequence[ProtectEntityDescription],
) -> list[BaseProtectEntity]:
    """Build the entities a public device supports without a private fill.

    Only descriptions reading a public value qualify; the required field and
    the capability are checked against the public object. The public API has
    no permission model, so ``ufp_perm`` does not apply.
    """
    entities: list[BaseProtectEntity] = []
    for description in descs:
        if (
            not description.is_public_value
            or not description.has_required_public(public)
            or not _async_capability_supported(public, None, description)
        ):
            continue
        entities.append(
            klass(
                data,
                device=cast(ProtectDeviceType, public),
                description=description,
            )
        )
        _LOGGER.debug(
            "Adding %s entity %s for %s",
            klass.__name__,
            description.key,
            public.display_name,
        )
    return entities


@callback
def _async_device_entities(
    data: ProtectData,
    klass: type[BaseProtectEntity],
    model_type: ModelType,
    descs: Sequence[ProtectEntityDescription],
    unadopted_descs: Sequence[ProtectEntityDescription] | None = None,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
    public_device: PublicDeviceModel | None = None,
) -> list[BaseProtectEntity]:
    if not descs and not unadopted_descs:
        return []

    pairs: Iterable[tuple[PublicDeviceModel | None, ProtectAdoptableDeviceModel | None]]
    if ufp_device is not None:
        pairs = [(data.async_get_public_device(ufp_device), ufp_device)]
    elif public_device is not None:
        pairs = [(public_device, None)]
    else:
        pairs = data.get_public_devices(model_type, ignore_unadopted=False)

    api = data.api
    is_public_only = api.is_public_only
    auth_user = None if is_public_only else api.bootstrap.auth_user
    entities: list[BaseProtectEntity] = []
    for public, device in pairs:
        if device is None:
            # Hybrid defers a device without private fill to the adopt dispatch.
            if is_public_only and public is not None:
                entities.extend(_async_public_only_entities(data, klass, public, descs))
            continue
        if TYPE_CHECKING:
            assert auth_user is not None
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
                        description.key,
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

            if not _async_capability_supported(public, device, description):
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
                description.key,
                device.display_name,
            )

    return entities


_ALL_MODEL_TYPES = (
    ModelType.CAMERA,
    ModelType.LIGHT,
    ModelType.SENSOR,
    ModelType.VIEWPORT,
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
    public_device: PublicDeviceModel | None = None,
) -> list[BaseProtectEntity]:
    """Generate a list of all the device entities.

    ``ufp_device`` builds for one adopted private device, ``public_device`` for
    one public device without private fill (public-only mode).
    """
    device = ufp_device if ufp_device is not None else public_device
    if device is None:
        entities: list[BaseProtectEntity] = []
        for model_type in _ALL_MODEL_TYPES:
            descs = _combine_model_descs(model_type, model_descriptions, all_descs)
            entities.extend(
                _async_device_entities(data, klass, model_type, descs, unadopted_descs)
            )
        return entities

    device_model_type = device.model
    assert device_model_type is not None
    # Runtime adoption must honor the same model-type allowlist as initial setup,
    # so unsupported devices (e.g. AI Port) get no entities when adopted live.
    if device_model_type not in _ALL_MODEL_TYPES:
        return []
    descs = _combine_model_descs(device_model_type, model_descriptions, all_descs)
    return _async_device_entities(
        data,
        klass,
        device_model_type,
        descs,
        unadopted_descs,
        ufp_device,
        public_device,
    )


class BaseProtectEntity(Entity):
    """Base class for UniFi protect entities."""

    device: ProtectDeviceType

    _attr_should_poll = False
    _attr_attribution = DEFAULT_ATTRIBUTION
    _state_attrs: tuple[str, ...] = ("_attr_available",)
    _attr_has_entity_name = True
    _async_get_ufp_enabled: Callable[[ProtectAdoptableDeviceModel], bool] | None = None
    _async_get_ufp_public_enabled: Callable[[PublicDeviceModel], bool] | None = None
    # Cached public-API object for descriptions migrated to the public path
    # (set ``ufp_public_value``); ``None`` until primed/refreshed.
    _ufp_public_obj: PublicDeviceModel | None = None
    _ufp_uses_public: bool = False
    # Values derived from the public events websocket (detection booleans,
    # public event entities) additionally require that websocket to be healthy.
    _ufp_requires_events_ws: bool = False
    # False when the entity was built from a public object alone (public-only
    # mode); ``device`` then holds that object and private fields are absent.
    _ufp_has_private: bool = True

    def __init__(
        self,
        data: ProtectData,
        device: ProtectDeviceType | PublicDeviceModel,
        description: EntityDescription | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.data = data
        if isinstance(device, PublicDeviceModel):
            self._ufp_has_private = False
            self._ufp_public_obj = device
        # The base keys on the mac, which both model trees carry.
        self.device = cast(ProtectDeviceType, device)

        if description is None:
            self._attr_unique_id = self.device.mac
            self._attr_name = None
        else:
            self.entity_description = description
            self._attr_unique_id = f"{self.device.mac}_{description.key}"
            if isinstance(description, ProtectEntityDescription):
                self._async_get_ufp_enabled = description.get_ufp_enabled
                self._async_get_ufp_public_enabled = description.ufp_public_enabled_fn

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

        if self._ufp_uses_public:
            # Migrated entities are fully public: availability tracks the public
            # websocket health and the public object's state (CONNECTED only;
            # CONNECTING/DISCONNECTED/UNKNOWN and a missing object read as
            # unavailable), independent of the private connection. Values fed by
            # the events websocket also require it to be healthy — the devices
            # websocket keeps the device state fresh, but only the events stream
            # carries the detections. An optional ``ufp_public_enabled_fn`` gate
            # then mirrors ``ufp_enabled`` against the public object (e.g. a
            # sensor feature toggled off).
            public_obj = self._ufp_public_obj
            if (
                self.data.last_public_update_success
                and (
                    not self._ufp_requires_events_ws
                    or self.data.last_events_update_success
                )
                and public_obj is not None
                and public_obj.state is DeviceState.CONNECTED
            ):
                get_public_enabled = self._async_get_ufp_public_enabled
                available = get_public_enabled is None or get_public_enabled(public_obj)
            else:
                available = False
        elif device.model is ModelType.NVR:
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
    def _ufp_set_target(self) -> ProtectDeviceType | PublicDeviceModel:
        """Return the object a description's setter is called on.

        A migrated description writes through the public object it reads from,
        in both connection modes; the private device serves the rest.
        """
        if not self._ufp_uses_public:
            return self.device
        if (public := self._ufp_public_obj) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_available",
                translation_placeholders={"device_name": self.device.display_name},
            )
        return public

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
                _LOGGER.debug(
                    "Updating state [%s] %s -> %s",
                    self.entity_id,
                    previous_attrs,
                    tuple(getter() for getter in self._state_getters),
                )
            self.async_write_ha_state()

    @callback
    def _async_public_updated(self, obj: PublicDeviceModel | None) -> None:
        """Handle a public devices WS update for a migrated value.

        ``obj`` is the refreshed public object from a WS message; ``None`` when
        there is no object to pass (a websocket state change, a delete event,
        or a frame the library could not merge). The object is then re-read
        from the bootstrap: a deleted device reads as missing (the entity goes
        unavailable), and after a reconnect a value that changed during the
        outage is picked up.
        """
        self._ufp_public_obj = (
            obj if obj is not None else self.data.async_get_public_device(self.device)
        )
        self._async_updated_event(self.device)

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.data.async_subscribe(self.device.mac, self._async_updated_event)
        )
        # Not every entity carries an entity_description (e.g. cameras), so getattr.
        description = getattr(self, "entity_description", None)
        if isinstance(description, ProtectEntityDescription):
            if description.is_public_value:
                self._ufp_uses_public = True
            if description.ufp_event_driven:
                self._ufp_requires_events_ws = True
        # ``_ufp_uses_public`` may also be declared as a class attribute by
        # entities driven by the public API without a migrated value (the
        # public event entities).
        if self._ufp_uses_public:
            self._ufp_public_obj = self.data.async_get_public_device(self.device)
            self.async_on_remove(
                self.data.async_subscribe_public(
                    self.device.mac, self._async_public_updated
                )
            )
        self._async_update_device_from_protect(self.device)


class ProtectIsOnEntity(BaseProtectEntity):
    """Base class for entities with is_on property."""

    _state_attrs: tuple[str, ...] = ("_attr_available", "_attr_is_on")
    _attr_is_on: bool | None
    entity_description: ProtectEntityDescription

    @override
    def _async_update_device_from_protect(
        self, device: ProtectAdoptableDeviceModel | NVR
    ) -> None:
        super()._async_update_device_from_protect(device)
        was_on = self._attr_is_on
        value = self.entity_description.get_value(device, self._ufp_public_obj)
        if was_on != (is_on := value is True):
            self._attr_is_on = is_on


class ProtectDeviceEntity(BaseProtectEntity):
    """Base class for UniFi protect entities."""

    @callback
    @override
    def _async_set_device_info(self) -> None:
        if not self._ufp_has_private:
            # market_name/firmware/URL are private-only; the NVR link uses the
            # device id registered at setup.
            public = self._ufp_public_obj
            if TYPE_CHECKING:
                assert public is not None
            self._attr_device_info = DeviceInfo(
                name=public.display_name,
                model=public.type,
                model_id=public.type,
                manufacturer=DEFAULT_BRAND,
                connections={(dr.CONNECTION_NETWORK_MAC, public.mac)},
                via_device_id=self.data.nvr_device_id,
            )
            return
        self._attr_device_info = DeviceInfo(
            name=self.device.display_name,
            manufacturer=DEFAULT_BRAND,
            model=self.device.market_name or self.device.type,
            model_id=self.device.type,
            via_device_id=self.data.nvr_device_id,
            sw_version=self.device.firmware_version,
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            configuration_url=self.device.protect_url,
        )


class ProtectNVREntity(BaseProtectEntity):
    """Base class for unifi protect entities."""

    device: NVR

    @callback
    @override
    def _async_set_device_info(self) -> None:
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, self.device.mac)},
            manufacturer=DEFAULT_BRAND,
            name=self.device.display_name,
            model=self.device.market_name or self.device.type,
            model_id=self.device.type,
            sw_version=str(self.device.version),
            configuration_url=self.device.api.base_url,
        )


class EventEntityMixin(ProtectDeviceEntity):
    """Adds motion event attributes to sensor."""

    entity_description: ProtectEventMixin
    _unrecorded_attributes = frozenset(
        {ATTR_EVENT_ID, ATTR_EVENT_SCORE, ATTR_SMART_DETECT_TYPES}
    )
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


@dataclass(frozen=True, kw_only=True)
class ProtectEntityDescription(EntityDescription, Generic[T]):  # noqa: UP046
    """Base class for protect entity descriptions."""

    ufp_required_field: str | None = None
    ufp_value: str | None = None
    ufp_value_fn: Callable[[T], Any] | None = None
    ufp_public_value: str | None = None
    # Callable variant of ``ufp_public_value`` for public values needing a transform.
    ufp_public_value_fn: Callable[[PublicDeviceModel], Any] | None = None
    # True when the public value is derived from the events websocket (the
    # detection booleans); availability then also tracks that websocket.
    ufp_event_driven: bool = False
    ufp_enabled: str | None = None
    # Public counterpart of ``ufp_enabled``; a callable because public enablement
    # is often compound (e.g. mount type plus a settings flag).
    ufp_public_enabled_fn: Callable[[PublicDeviceModel], bool] | None = None
    # Capability required to create the entity: a sensor capability is checked
    # against the public capability map (without one every description is
    # created), a smart-detect type against the camera's advertised types.
    ufp_capability: SensorFeatureCapability | SmartDetectObjectType | None = None
    ufp_perm: PermRequired | None = None

    # The below are set in __post_init__
    has_required: Callable[[T], bool] = bool
    # ``ufp_required_field`` against the public object; an attribute path the
    # public model lacks reads as False, so private-only descriptions are
    # skipped in public-only mode.
    has_required_public: Callable[[PublicDeviceModel], bool] = bool
    get_ufp_enabled: Callable[[T], bool] | None = None
    get_ufp_public_value: Callable[[PublicDeviceModel], Any] | None = None

    @property
    def is_public_value(self) -> bool:
        """Whether the value is read from the public object."""
        return self.ufp_public_value is not None or self.ufp_public_value_fn is not None

    def get_ufp_value(self, obj: T) -> Any:
        """Return value from UniFi Protect device; overridden in __post_init__."""
        # ufp_value or ufp_value_fn are required, the
        # RuntimeError is to catch any issues in the code
        # with new descriptions.
        raise RuntimeError(  # pragma: no cover
            f"`ufp_value` or `ufp_value_fn` is required for {self}"
        )

    def get_value(self, obj: T, public_obj: PublicDeviceModel | None = None) -> Any:
        """Return the value, reading from the public object when migrated.

        A migrated description sets ``ufp_public_value`` (or ``ufp_public_value_fn``)
        and drops the private ``ufp_value``: the value comes only from the public
        object, or ``None`` when it is absent (the entity is then marked
        unavailable).
        """
        if (fn := self.ufp_public_value_fn) is not None:
            return None if public_obj is None else fn(public_obj)
        if (getter := self.get_ufp_public_value) is not None:
            return None if public_obj is None else getter(public_obj)
        return self.get_ufp_value(obj)

    def __post_init__(self) -> None:
        """Override get_ufp_value, has_required, and get_ufp_enabled if required."""
        _setter = partial(object.__setattr__, self)

        if (ufp_value := self.ufp_value) is not None:
            _setter("get_ufp_value", make_value_getter(ufp_value))
        elif (ufp_value_fn := self.ufp_value_fn) is not None:
            _setter("get_ufp_value", ufp_value_fn)

        if (ufp_public_value := self.ufp_public_value) is not None:
            _setter("get_ufp_public_value", make_value_getter(ufp_public_value))

        if (ufp_enabled := self.ufp_enabled) is not None:
            _setter("get_ufp_enabled", make_enabled_getter(ufp_enabled))

        if (ufp_required_field := self.ufp_required_field) is not None:
            _setter("has_required", make_required_getter(ufp_required_field))
            _setter(
                "has_required_public",
                partial(get_nested_attr_as_bool, tuple(ufp_required_field.split("."))),
            )


@dataclass(frozen=True, kw_only=True)
class ProtectEventMixin(ProtectEntityDescription[T]):
    """Mixin for events."""

    ufp_event_obj: str | None = None
    ufp_obj_type: SmartDetectObjectType | None = None

    def get_event_obj(self, obj: T) -> Event | None:
        """Return value from UniFi Protect device."""
        return None

    def has_matching_smart(self, event: Event) -> bool:
        """Determine if the detection type is a match."""
        return (
            not (obj_type := self.ufp_obj_type) or obj_type in event.smart_detect_types
        )

    @override
    def __post_init__(self) -> None:
        """Override get_event_obj if ufp_event_obj is set."""
        if (_ufp_event_obj := self.ufp_event_obj) is not None:
            object.__setattr__(self, "get_event_obj", attrgetter(_ufp_event_obj))
        super().__post_init__()


@dataclass(frozen=True, kw_only=True)
class ProtectSettableKeysMixin(ProtectEntityDescription[T]):
    """Mixin for settable values."""

    # Called on the object the value is read from: the public object for a
    # migrated description, the private device otherwise.
    ufp_set_method: str | None = None
    ufp_set_method_fn: Callable[[Any, Any], Coroutine[Any, Any, None]] | None = None

    async def ufp_set(self, obj: T | PublicDeviceModel, value: Any) -> None:
        """Set value for UniFi Protect device."""
        _LOGGER.debug("Setting %s to %s for %s", self.key, value, obj.display_name)
        if self.ufp_set_method is not None:
            await getattr(obj, self.ufp_set_method)(value)
        elif self.ufp_set_method_fn is not None:
            await self.ufp_set_method_fn(obj, value)
