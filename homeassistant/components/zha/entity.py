"""Entity for Zigbee Home Automation."""

import asyncio
from collections.abc import Callable, Iterator
import dataclasses
from enum import IntFlag
from functools import partial
import logging
from typing import Any, override

from propcache.api import cached_property
from zha.application.platforms import EntityStateChangedEvent, ZclPlatformEntity
from zha.mixins import LogMixin
from zigpy.zcl import ClusterType

from homeassistant.const import STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import Context, State, callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import CONTEXT_RECENT_TIME_SECONDS, Entity
from homeassistant.helpers.group import IntegrationSpecificGroup
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType, Undefined

from .const import DOMAIN
from .helpers import (
    SIGNAL_REMOVE_ENTITIES,
    SIGNAL_REMOVE_ENTITY,
    EntityData,
    convert_zha_error_to_ha_error,
)

_LOGGER = logging.getLogger(__name__)


class ZHAEntity(LogMixin, RestoreEntity, Entity):
    """ZHA eitity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _context_expected_state: StateType = None
    _context_expected_state_matched: bool = False
    _group_target_cluster_ids: frozenset[int] = frozenset()
    remove_future: asyncio.Future[Any]

    def __init__(self, entity_data: EntityData, *args, **kwargs) -> None:
        """Init ZHA entity."""
        super().__init__(*args, **kwargs)
        self.entity_data: EntityData = entity_data
        self._unsubs: list[Callable[[], None]] = []
        self._zha_state = self.entity_data.entity.state

        if self.entity_data.entity.icon is not None:
            # Only custom quirks will realistically set an icon
            self._attr_icon = self.entity_data.entity.icon

        meta = self._zha_state
        self._attr_unique_id = meta.unique_id

        if self.entity_data.is_group_entity:
            group_proxy = self.entity_data.group_proxy
            assert group_proxy is not None
            platform = self.entity_data.entity.PLATFORM
            unique_ids = [
                entity.identifiers.unique_id
                for member in group_proxy.group.members
                for entity in member.associated_entities
                if platform == entity.PLATFORM
            ]
            self.group = IntegrationSpecificGroup(self, unique_ids)

        if meta.entity_category is not None:
            self._attr_entity_category = EntityCategory(meta.entity_category)

        self._attr_entity_registry_enabled_default = (
            meta.entity_registry_enabled_default
        )

        if meta.translation_key is not None:
            self._attr_translation_key = meta.translation_key

        if meta.translation_placeholders is not None:
            self._attr_translation_placeholders = meta.translation_placeholders

        self._update_capability_attrs()

    @cached_property
    @override
    def name(self) -> str | Undefined | None:
        """Return the name of the entity.

        Built-in quirks have translations in HA, so those are used.
        Custom quirks with new translation keys won't have translations.
        For them, the fallback name should be used instead.
        If a device class is set but no translation key,
        the device class name is used.
        """
        # Group entities take the name of their group device
        if self.entity_data.is_group_entity:
            return None

        meta = self._zha_state
        if meta.primary:
            self._attr_name = None
            return super().name

        # If we do not have a fallback_name, use default behavior
        if meta.fallback_name is None:
            return super().name

        # If we do not have a translation key, only use fallback_name
        # if device class is also missing
        if meta.translation_key is None:
            if super().name in (Undefined, None):
                self._attr_name = meta.fallback_name
            return super().name

        # If we do have a translation key, only use fallback_name
        # if translation is missing (custom quirks)
        if not (
            (translation_key := self._name_translation_key) is not None
            and translation_key in self.platform_data.platform_translations
        ):
            self._attr_name = meta.fallback_name
        return super().name

    @property
    @override
    def available(self) -> bool:
        """Return entity availability."""
        return self._zha_state.available

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        # Group entities have their own device linked via the coordinator
        if self.entity_data.is_group_entity:
            group_proxy = self.entity_data.group_proxy
            assert group_proxy is not None
            return group_proxy.device_info

        zha_device_info = self.entity_data.device_proxy.device_info
        ieee = zha_device_info["ieee"]

        return DeviceInfo(
            connections={(CONNECTION_ZIGBEE, ieee)},
            identifiers={(DOMAIN, ieee)},
            manufacturer=zha_device_info["manufacturer"],
            model=zha_device_info["model"],
            name=zha_device_info["name"],
        )

    def _update_capability_attrs(self) -> None:
        """Re-derive capability `_attr_*` attributes from the cached state."""

    def _iter_group_member_entities(
        self, target_cluster_ids: frozenset[int]
    ) -> Iterator[ZHAEntity]:
        """Yield registered HA entities for members controlled by this group entity."""
        group_proxy = self.entity_data.group_proxy
        assert group_proxy is not None
        gateway_proxy = group_proxy.gateway_proxy
        member_unique_ids = set(group_proxy.group.all_member_entity_unique_ids)
        for ieee in {member.device.ieee for member in group_proxy.group.members}:
            for entity_ref in gateway_proxy.ha_entity_refs.get(ieee, ()):
                zha_entity = entity_ref.entity_data.entity
                if (
                    zha_entity.unique_id in member_unique_ids
                    and isinstance(zha_entity, ZclPlatformEntity)
                    and any(
                        zha_entity.targets_cluster(cluster_id, ClusterType.Server)
                        and cluster_id in zha_entity.endpoint.zigpy_endpoint.in_clusters
                        for cluster_id in target_cluster_ids
                    )
                ):
                    yield entity_ref.ha_entity

    @callback
    def async_set_group_context(
        self,
        context: Context,
        context_set: float | None,
        expected_state: StateType,
    ) -> None:
        """Set context propagated from a ZHA group entity."""
        current_state = self.state if self.available else STATE_UNAVAILABLE
        has_pending_transition = (
            self._context is not None
            and self._context_expected_state is not None
            and not self._context_expected_state_matched
            and self._context_set is not None
            and context_set is not None
            and context_set - self._context_set <= CONTEXT_RECENT_TIME_SECONDS
        )
        self._context = context
        self._context_set = context_set
        self._context_expected_state = expected_state
        self._context_expected_state_matched = (
            current_state == expected_state and not has_pending_transition
        )

    @callback
    def _propagate_group_context(
        self,
        expected_state: StateType,
        target_cluster_ids: frozenset[int] | None = None,
    ) -> None:
        """Propagate the active group context and its expected target state to members."""
        if not self.entity_data.is_group_entity or self._context is None:
            return
        cluster_ids = (
            self._group_target_cluster_ids
            if target_cluster_ids is None
            else target_cluster_ids
        )
        if not cluster_ids:
            return
        for member_entity in self._iter_group_member_entities(cluster_ids):
            member_entity.async_set_group_context(
                self._context,
                self._context_set,
                expected_state,
            )

    @callback
    @override
    def async_set_context(self, context: Context) -> None:
        """Set the context the entity currently operates under."""
        super().async_set_context(context)
        self._context_expected_state = None
        self._context_expected_state_matched = False

    @callback
    def _handle_zha_entity_state_changed(self, event: EntityStateChangedEvent) -> None:
        """Handle a state change reported by the ZHA library entity."""
        self.debug("Handling event from entity: %s", event)
        self._zha_state = dataclasses.replace(self._zha_state, **event.state_diff)
        self._update_capability_attrs()
        current_state = self.state if self.available else STATE_UNAVAILABLE
        if self._context_expected_state is not None:
            if current_state == self._context_expected_state:
                self._context_expected_state_matched = True
            elif self._context_expected_state_matched:
                self._context = None
                self._context_set = None
                self._context_expected_state = None
                self._context_expected_state_matched = False
            else:
                # Withhold group context from a mismatched report without discarding
                # a still-pending command before its matching report arrives.
                pending_context = self._context
                pending_context_set = self._context_set
                self._context = None
                self._context_set = None
                try:
                    self.async_write_ha_state()
                finally:
                    self._context = pending_context
                    self._context_set = pending_context_set
                return
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        self.remove_future = self.hass.loop.create_future()
        remove_signal = (
            f"{SIGNAL_REMOVE_ENTITIES}_group_{self.entity_data.group_proxy.group.group_id}"
            if self.entity_data.is_group_entity
            and self.entity_data.group_proxy is not None
            else f"{SIGNAL_REMOVE_ENTITIES}_{self.entity_data.device_proxy.device.ieee}"
        )
        self._unsubs.append(
            async_dispatcher_connect(
                self.hass,
                remove_signal,
                partial(self.async_remove, force_remove=True),
            )
        )
        self._unsubs.append(
            async_dispatcher_connect(
                self.hass,
                (
                    f"{SIGNAL_REMOVE_ENTITY}_"
                    f"{self.entity_data.entity.PLATFORM}_{self.unique_id}"
                ),
                self.async_remove,
            )
        )
        self.entity_data.device_proxy.gateway_proxy.register_entity_reference(self)

        if (state := await self.async_get_last_state()) is not None:
            self.restore_external_state_attributes(state)

        # The subscription synchronously delivers the full current state as its
        # first event, establishing a baseline coherent with subsequent diffs.
        self._unsubs.append(
            self.entity_data.entity.subscribe_state(
                self._handle_zha_entity_state_changed
            )
        )

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Update the gateway entity reference to the new entity_id."""
        super().async_entity_id_changed(old_entity_id)
        self.entity_data.device_proxy.gateway_proxy.update_entity_reference(
            self, old_entity_id
        )

    @callback
    def restore_external_state_attributes(self, state: State) -> None:
        """Restore ephemeral external state from Home Assistant back into ZHA."""

        # Some operations rely on extra state that is not maintained in the ZCL
        # attribute cache. Until ZHA is able to maintain its own persistent state (or
        # provides a more generic hook to utilize HA to do this), we directly restore
        # them.

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Disconnect entity object when removed."""
        for unsub in self._unsubs[:]:
            unsub()
            self._unsubs.remove(unsub)
        self.entity_data.device_proxy.gateway_proxy.remove_entity_reference(self)
        await super().async_will_remove_from_hass()
        self.remove_future.set_result(True)

    @convert_zha_error_to_ha_error()
    async def async_update(self) -> None:
        """Update the entity."""
        await self.entity_data.entity.async_update()
        self.async_write_ha_state()

    def log(self, level: int, msg: str, *args, **kwargs):
        """Log a message."""
        if not _LOGGER.isEnabledFor(level):
            # Avoid building the prefixed message and args tuple for disabled
            # levels; this runs for every entity event via
            # _handle_zha_entity_state_changed.
            return
        msg = f"%s: {msg}"
        args = (self.entity_id, *args)
        _LOGGER.log(level, msg, *args, **kwargs)


class ZHASupportedFeaturesEntity(ZHAEntity):
    """ZHA entity whose state carries a `supported_features` flag to translate."""

    @override
    def _update_capability_attrs(self) -> None:
        """Re-derive capability `_attr_*` attributes from the cached state."""
        self._attr_supported_features = self._convert_supported_features(
            self._zha_state.supported_features
        )

    @staticmethod
    def _convert_supported_features(zha_features: IntFlag) -> IntFlag:
        """Translate ZHA feature flags into their HA equivalents."""
        raise NotImplementedError
