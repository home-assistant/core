"""Base class for Ring entity."""

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Concatenate, Generic, TypeVar, cast

from ring_doorbell import (
    AuthenticationError,
    RingDevices,
    RingError,
    RingGeneric,
    RingTimeout,
)

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    CoordinatorEntity,
)

from .const import ATTRIBUTION, DOMAIN
from .coordinator import RingDataCoordinator, RingListenCoordinator

RingDeviceT = TypeVar("RingDeviceT", bound=RingGeneric, default=RingGeneric)

_RingCoordinatorT = TypeVar(
    "_RingCoordinatorT",
    bound=(RingDataCoordinator | RingListenCoordinator),
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DeprecatedInfo:
    """Class to define deprecation info for deprecated entities."""

    new_platform: Platform
    breaks_in_ha_version: str


@dataclass(frozen=True, kw_only=True)
class RingEntityDescription(EntityDescription):
    """Base class for a ring entity description."""

    deprecated_info: DeprecatedInfo | None = None


def exception_wrap[_RingBaseEntityT: RingBaseEntity[Any, Any], **_P, _R](
    async_func: Callable[Concatenate[_RingBaseEntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_RingBaseEntityT, _P], Coroutine[Any, Any, _R]]:
    """Define a wrapper to catch exceptions and raise HomeAssistant errors."""

    async def _wrap(self: _RingBaseEntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return await async_func(self, *args, **kwargs)
        except AuthenticationError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_authentication",
            ) from err
        except RingTimeout as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_timeout",
            ) from err
        except RingError as err:
            _LOGGER.debug(
                "Error calling %s in platform %s: ", async_func.__name__, self.platform
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
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
    platform: Platform,
    unique_id: str,
    entity_description: RingEntityDescription,
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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},  # device_id is the mac
            manufacturer="Ring",
            model=device.model,
            name=device.name,
        )


class RingEntity(RingBaseEntity[RingDataCoordinator, RingDeviceT], CoordinatorEntity):
    """Implementation for Ring devices."""

    def _get_coordinator_data(self) -> RingDevices:
        return self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        self._device = cast(
            RingDeviceT,
            self._get_coordinator_data().get_device(self._device.device_api_id),
        )
        super()._handle_coordinator_update()
