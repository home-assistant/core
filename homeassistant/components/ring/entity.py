"""Base class for Ring entity."""

from collections.abc import Awaitable, Callable, Coroutine, Iterable
from dataclasses import dataclass
from typing import Any, Concatenate, Generic, Self, cast

from ring_doorbell import (
    AuthenticationError,
    RingDevices,
    RingError,
    RingGeneric,
    RingTimeout,
)
from typing_extensions import TypeVar

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    CoordinatorEntity,
)

from . import RingConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import RingDataCoordinator, RingListenCoordinator

RingDeviceT = TypeVar("RingDeviceT", bound=RingGeneric, default=RingGeneric)

_RingCoordinatorT = TypeVar(
    "_RingCoordinatorT",
    bound=(RingDataCoordinator | RingListenCoordinator),
)


@dataclass(slots=True)
class DeprecatedInfo:
    """Class to define deprecation info for deprecated entities."""

    new_platform: Platform
    breaks_in_ha_version: str


@dataclass(frozen=True, kw_only=True)
class RingEntityDescription(EntityDescription, Generic[RingDeviceT]):
    """Base class for a ring entity description."""

    deprecated_info: DeprecatedInfo | None = None
    exists_fn: Callable[[RingDeviceT], bool]
    unique_id_fn: Callable[[Self, RingDeviceT], str] = (
        lambda self, device: f"{device.device_api_id}-{self.key}"
    )
    dynamic_setting_description: str = "other settings"


def exception_wrap[_RingBaseEntityT: RingBaseEntity[Any, Any], **_P, _R](
    async_func: Callable[Concatenate[_RingBaseEntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_RingBaseEntityT, _P], Coroutine[Any, Any, _R]]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    async def _wrap(self: _RingBaseEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await async_func(self, *args, **kwargs)
        except AuthenticationError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(err) from err
        except RingTimeout as err:
            raise HomeAssistantError(
                f"Timeout communicating with API {async_func}: {err}"
            ) from err
        except RingError as err:
            raise HomeAssistantError(
                f"Error communicating with API{async_func}: {err}"
            ) from err

    return _wrap


def refresh_after[_RingEntityT: RingEntity[Any], **_P](
    func: Callable[Concatenate[_RingEntityT, _P], Awaitable[None]],
) -> Callable[Concatenate[_RingEntityT, _P], Coroutine[Any, Any, None]]:
    """Define a wrapper to handle api call errors or refresh after success."""

    @exception_wrap
    async def _wrap(self: _RingEntityT, *args: _P.args, **kwargs: _P.kwargs) -> None:
        await func(self, *args, **kwargs)
        await self.coordinator.async_request_refresh()

    return _wrap


def async_check_create_deprecated(
    hass: HomeAssistant,
    platform: str,
    unique_id: str,
    entity_description: RingEntityDescription[RingDeviceT],
) -> bool:
    """Return true if the entitty should be created based on the deprecated_info.

    If deprecated_info is not defined will return true.
    If entity not yet created will return false.
    If entity disabled will delete it and return false.
    Otherwise will return true and create issues for scripts or automations.
    """
    if not entity_description.deprecated_info:
        return True

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        platform,
        DOMAIN,
        unique_id,
    )
    if not entity_id:
        return False

    entity_entry = ent_reg.async_get(entity_id)
    assert entity_entry
    if entity_entry.disabled:
        # If the entity exists and is disabled then we want to remove
        # the entity so that the user is just using the new entity.
        ent_reg.async_remove(entity_id)
        return False

    # Check for issues that need to be created
    entity_automations = automations_with_entity(hass, entity_id)
    entity_scripts = scripts_with_entity(hass, entity_id)
    if entity_automations or entity_scripts:
        deprecated_info = entity_description.deprecated_info
    for item in entity_automations + entity_scripts:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_entity_{entity_id}_{item}",
            breaks_in_ha_version=deprecated_info.breaks_in_ha_version,
            is_fixable=False,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_entity",
            translation_placeholders={
                "entity": entity_id,
                "info": item,
                "platform": platform,
                "new_platform": deprecated_info.new_platform,
            },
        )
    return True


class RingBaseEntity(
    BaseCoordinatorEntity[_RingCoordinatorT], Generic[_RingCoordinatorT, RingDeviceT]
):
    """Base implementation for Ring device."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: _RingCoordinatorT,
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(coordinator, context=device.id)
        self._device = device
        self._attr_extra_state_attributes = {}
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},  # device_id is the mac
            manufacturer="Ring",
            model=device.model,
            name=device.name,
        )
        self._removed = False

    async def async_removed_from_registry(self) -> None:
        """Run when entity has been removed from entity registry."""
        await self.platform.async_remove_entity(self.entity_id)
        self._removed = True


class RingEntity(RingBaseEntity[RingDataCoordinator, RingDeviceT], CoordinatorEntity):
    """Implementation for Ring devices."""

    unique_id: str

    def __init__(
        self,
        device: RingDeviceT,
        coordinator: RingDataCoordinator,
        description: RingEntityDescription[RingDeviceT],
    ) -> None:
        """Initialize a sensor for Ring device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = description.unique_id_fn(description, device)

    def _get_coordinator_data(self) -> RingDevices:
        return self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._removed:
            return
        self._device = cast(
            RingDeviceT,
            self._get_coordinator_data().get_device(self._device.device_api_id),
        )
        super()._handle_coordinator_update()

    @classmethod
    def process_entities[
        _D: RingEntityDescription[Any],
    ](
        cls,
        hass: HomeAssistant,
        coordinator: RingDataCoordinator,
        *,
        entry: RingConfigEntry,
        async_add_entities: AddEntitiesCallback,
        domain: str,
        descriptions: Iterable[_D],
        **kwargs: Any,
    ) -> None:
        """Process device entities."""
        processed_device_entities: dict[int, dict[str, RingEntity[RingDeviceT]]] = {}

        def _entities_for_device(device: RingDeviceT) -> list[RingEntity[RingDeviceT]]:
            return [
                cls(device, coordinator, description, **kwargs)
                for description in descriptions
                if description.exists_fn(device)
                and async_check_create_deprecated(
                    hass,
                    domain,
                    description.unique_id_fn(description, device),
                    description,
                )
            ]

        def _async_delete_entities(entities: list[RingEntity[RingDeviceT]]) -> None:
            """Delete entities for entities not existing."""
            entity_registry = er.async_get(hass)
            device_ids: set[str] = set()
            for entity in entities:
                entity_id = entity_registry.async_get_entity_id(
                    domain, DOMAIN, entity.unique_id
                )
                if entity_id:
                    ent_reg = entity_registry.async_get(entity_id)
                    if ent_reg and ent_reg.device_id:
                        device_ids.add(ent_reg.device_id)
                    entity_registry.async_remove(entity_id)
            for device_id in device_ids:
                ents = er.async_entries_for_device(entity_registry, device_id)
                if not ents:
                    device_registry = dr.async_get(hass)
                    device_registry.async_update_device(
                        device_id, remove_config_entry_id=entry.entry_id
                    )

        def _async_entity_listener() -> None:
            """Handle additions/deletions of entities."""
            received_devices = set(coordinator.device_api_ids)
            processed_devices = set(processed_device_entities.keys())
            new_devices = received_devices - processed_devices
            removed_devices = processed_devices - received_devices
            entities_to_add = []
            entities_to_remove = []

            # process entity changes for already added devices.
            for device_api_id in received_devices:
                if device_api_id in new_devices:
                    continue
                device = cast(
                    RingDeviceT,
                    coordinator.ring_api.devices().get_device(device_api_id),
                )
                processed_entities = processed_device_entities[device_api_id]
                received_entities = {
                    entity.unique_id: entity for entity in _entities_for_device(device)
                }
                entities_to_add.extend(
                    [
                        entity
                        for unique_id, entity in received_entities.items()
                        if unique_id not in processed_entities
                    ]
                )
                entities_to_remove.extend(
                    [
                        entity
                        for unique_id, entity in processed_entities.items()
                        if unique_id not in received_entities
                    ]
                )
                processed_device_entities[device_api_id] = received_entities

            # process entity changes for newly added devices.
            for device_api_id in new_devices:
                device = cast(
                    RingDeviceT,
                    coordinator.ring_api.devices().get_device(device_api_id),
                )
                entities = _entities_for_device(device)
                entities_to_add.extend(entities)
                processed_device_entities[device_api_id] = {
                    entity.unique_id: entity for entity in entities
                }

            # process entity changes for removed devices.
            for device_api_id in removed_devices:
                entities_to_remove.extend(
                    processed_device_entities.pop(device_api_id, {}).values()
                )
            if entities_to_add:
                async_add_entities(entities_to_add)
            if entities_to_remove:
                _async_delete_entities(entities_to_remove)

        def _async_clean_registry() -> None:
            """Clean entities at config entry load."""
            entity_registry = er.async_get(hass)
            entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
            unique_ids = [
                unique_id
                for entities in processed_device_entities.values()
                for unique_id in entities
            ]
            for reg_entry in entries:
                if (
                    reg_entry.domain == domain
                    and (unique_id := reg_entry.unique_id)
                    and unique_id not in unique_ids
                ):
                    entity_registry.async_remove(reg_entry.entity_id)

        coordinator.async_add_listener(_async_entity_listener)
        _async_entity_listener()
        _async_clean_registry()
