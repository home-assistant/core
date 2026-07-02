"""Infrared platform for manifest-matched ZHA IR hubs."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import time
from types import SimpleNamespace
from typing import override

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterEntity,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
)
from homeassistant.components.zha.const import DOMAIN as ZHA_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .codecs import decode_received_payload, encode_payload
from .const import DOMAIN
from .helpers import (
    ReceiveArmCommandSpec,
    SupportedDevice,
    get_cluster_by_id,
    get_ir_cluster,
    get_receive_spec,
    get_supported_devices,
)

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


def _resolve_cluster_availability(cluster: object | None) -> bool:
    """Resolve availability for zigpy and quirk cluster device objects."""
    if cluster is None:
        return False
    endpoint = getattr(cluster, "endpoint", None)
    device = getattr(endpoint, "device", None)
    if device is None:
        return False

    available_value = getattr(device, "available", None)
    if isinstance(available_value, bool):
        return available_value
    if callable(available_value):
        try:
            return bool(available_value())
        except Exception:
            return True

    is_available_value = getattr(device, "is_available", None)
    if isinstance(is_available_value, bool):
        return is_available_value
    if callable(is_available_value):
        try:
            return bool(is_available_value())
        except Exception:
            return True

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ZHA infrared entities from auto-detected supported endpoints."""
    supported_devices = await hass.async_add_executor_job(get_supported_devices, hass)
    entities: list[InfraredEmitterEntity | InfraredReceiverEntity] = [
        ZhaInfraredEmitterEntity(device)
        for device in supported_devices
        if device.profile.features.send_ir
    ]
    entities.extend(
        ZhaInfraredReceiverEntity(device)
        for device in supported_devices
        if device.profile.features.receive_ir
    )
    async_add_entities(entities)


class ZhaInfraredEmitterEntity(InfraredEmitterEntity):
    """Proxy infrared emitter backed by a matched ZHA IR hub."""

    _attr_has_entity_name = True
    _attr_translation_key = "infrared_emitter"

    def __init__(self, device: SupportedDevice) -> None:
        """Initialize the emitter entity."""
        self._device = device
        self._ieee = device.ieee
        self._endpoint_id = device.endpoint_id
        self._attr_unique_id = f"{self._ieee}-{self._endpoint_id}-infrared-emitter"
        self._attr_name = f"{device.name} IR emitter"

    @property
    def available(self) -> bool:
        """Return whether the underlying ZHA device is currently available."""
        cluster = get_ir_cluster(self.hass, self._device)
        return _resolve_cluster_availability(cluster)

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Associate this entity with the underlying ZHA device."""
        return {
            "identifiers": {(ZHA_DOMAIN, self._ieee)},
            "connections": {(dr.CONNECTION_ZIGBEE, self._ieee)},
        }

    @override
    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an infrared command over profile-defined cluster transport."""
        cluster = get_ir_cluster(self.hass, self._device)
        if cluster is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ir_cluster_missing",
            )

        payload = encode_payload(
            codec_name=self._device.profile.codec.name,
            timings=command.get_raw_timings(),
            modulation=command.modulation,
        )
        _LOGGER.debug(
            "zha_infrared send step=encode_done entity=%s codec=%s payload_len=%s expect_reply=%s",
            self.entity_id,
            self._device.profile.codec.name,
            len(payload),
            self._device.profile.transport.expect_reply,
        )
        try:
            _LOGGER.debug(
                "zha_infrared send step=cluster_command_start entity=%s cluster_cmd_id=%s arg=%s",
                self.entity_id,
                self._device.profile.transport.command_id,
                self._device.profile.transport.command_arg,
            )
            await cluster.command(
                self._device.profile.transport.command_id,
                **{self._device.profile.transport.command_arg: payload},
                expect_reply=self._device.profile.transport.expect_reply,
            )
            _LOGGER.debug(
                "zha_infrared send step=cluster_command_done entity=%s cluster_cmd_id=%s",
                self.entity_id,
                self._device.profile.transport.command_id,
            )
        except Exception as err:
            _LOGGER.debug(
                "zha_infrared send step=cluster_command_error entity=%s cluster_cmd_id=%s error=%s",
                self.entity_id,
                self._device.profile.transport.command_id,
                err,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_command_failed",
                translation_placeholders={"error": str(err)},
            ) from err


class ZhaInfraredReceiverEntity(InfraredReceiverEntity):
    """Infrared receiver entity for profile-based receive transports."""

    _attr_has_entity_name = True
    _attr_translation_key = "infrared_receiver"

    def __init__(self, device: SupportedDevice) -> None:
        """Initialize the receiver entity."""
        self._device = device
        self._ieee = device.ieee
        self._endpoint_id = device.endpoint_id
        self._attr_unique_id = f"{self._ieee}-{self._endpoint_id}-infrared-receiver"
        self._attr_name = f"{device.name} IR receiver"
        self._last_payload: str | None = None
        self._receive_lock = asyncio.Lock()
        self._unsub_receive: CALLBACK_TYPE | None = None
        self._unsub_arm: CALLBACK_TYPE | None = None
        self._subscriber_count = 0
        self._receive_listener_ref: int | None = None
        self._receive_listener = SimpleNamespace(
            attribute_updated=self._async_on_attribute_updated
        )
        self._arm_command_sent_monotonic: float | None = None
        self._last_arm_transport_command_monotonic: float | None = None
        self._poll_tick_counter = 0
        self._arm_tick_counter = 0

    @property
    def available(self) -> bool:
        """Return whether the underlying ZHA device is currently available."""
        cluster = get_ir_cluster(self.hass, self._device)
        return _resolve_cluster_availability(cluster)

    @property
    def device_info(self) -> dr.DeviceInfo:
        """Associate this entity with the underlying ZHA device."""
        return {
            "identifiers": {(ZHA_DOMAIN, self._ieee)},
            "connections": {(dr.CONNECTION_ZIGBEE, self._ieee)},
        }

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop receiving when entity is removed."""
        self._async_stop_receiving()
        self._subscriber_count = 0
        await super().async_will_remove_from_hass()

    @callback
    def _async_start_receiving(self) -> None:
        """Start polling for received signals."""
        if self._unsub_receive is not None or self._receive_listener_ref is not None:
            _LOGGER.debug(
                "zha_infrared receiver step=start_skip_already_started entity=%s",
                self.entity_id,
            )
            return
        receive_spec = get_receive_spec(self._device.profile)
        if receive_spec is None:
            _LOGGER.debug(
                "zha_infrared receiver step=start_skip_no_receive_spec entity=%s",
                self.entity_id,
            )
            return
        _LOGGER.debug(
            "zha_infrared receiver start: entity=%s method=%s",
            self.entity_id,
            receive_spec.method,
        )

        if receive_spec.method == "cluster_attribute_report":
            cluster = get_ir_cluster(self.hass, self._device)
            if cluster is None or not hasattr(cluster, "add_listener"):
                _LOGGER.debug(
                    "zha_infrared receiver step=start_report_fallback_to_poll entity=%s reason=%s",
                    self.entity_id,
                    "cluster_missing_or_no_listener",
                )
                self._unsub_receive = async_track_time_interval(
                    self.hass,
                    self._async_poll_received_signal,
                    timedelta(seconds=receive_spec.poll_interval_seconds),
                )
            else:
                self._receive_listener_ref = cluster.add_listener(self._receive_listener)
                _LOGGER.debug(
                    "zha_infrared receiver step=start_report_listener_attached entity=%s listener_ref=%s",
                    self.entity_id,
                    self._receive_listener_ref,
                )
        else:
            self._unsub_receive = async_track_time_interval(
                self.hass,
                self._async_poll_received_signal,
                timedelta(seconds=receive_spec.poll_interval_seconds),
            )
            _LOGGER.debug(
                "zha_infrared receiver step=start_poll_timer_attached entity=%s interval=%ss",
                self.entity_id,
                receive_spec.poll_interval_seconds,
            )

        if receive_spec.arm_command is not None:
            self.hass.async_create_task(self._async_force_rearm(None))
            self._unsub_arm = async_track_time_interval(
                self.hass,
                self._async_arm_interval_tick,
                timedelta(seconds=receive_spec.arm_command.repeat_interval_seconds),
            )
            _LOGGER.debug(
                "zha_infrared receiver step=start_arm_timer_attached entity=%s repeat_interval=%ss min_cmd_interval=%ss",
                self.entity_id,
                receive_spec.arm_command.repeat_interval_seconds,
                receive_spec.arm_command.min_command_interval_seconds,
            )

    @callback
    def _async_stop_receiving(self) -> None:
        """Stop polling for received signals."""
        _LOGGER.debug("zha_infrared receiver stop: entity=%s", self.entity_id)
        if self._unsub_receive is not None:
            self._unsub_receive()
            self._unsub_receive = None

        if self._unsub_arm is not None:
            self._unsub_arm()
            self._unsub_arm = None

        if self._receive_listener_ref is not None:
            cluster = get_ir_cluster(self.hass, self._device)
            if cluster is not None and hasattr(cluster, "remove_listener"):
                cluster.remove_listener(self._receive_listener_ref)
            self._receive_listener_ref = None

        self._arm_command_sent_monotonic = None
        self._last_arm_transport_command_monotonic = None
        self._poll_tick_counter = 0
        self._arm_tick_counter = 0

    @callback
    @override
    def async_subscribe_received_signal(
        self, signal_callback: Callable[[InfraredReceivedSignal], None]
    ) -> CALLBACK_TYPE:
        """Subscribe and lazily start receive polling on first subscriber."""
        unsub = super().async_subscribe_received_signal(signal_callback)
        self._subscriber_count += 1
        _LOGGER.debug(
            "zha_infrared receiver step=subscribe entity=%s subscribers=%s",
            self.entity_id,
            self._subscriber_count,
        )
        if self._subscriber_count == 1:
            self._async_start_receiving()

        removed = False

        @callback
        def _remove_callback() -> None:
            nonlocal removed
            if removed:
                return
            removed = True
            unsub()
            if self._subscriber_count:
                self._subscriber_count -= 1
            _LOGGER.debug(
                "zha_infrared receiver step=unsubscribe entity=%s subscribers=%s",
                self.entity_id,
                self._subscriber_count,
            )
            if self._subscriber_count == 0:
                self._async_stop_receiving()

        return _remove_callback

    async def _async_poll_received_signal(self, _: datetime) -> None:
        """Poll receive transport and dispatch signal if new payload is found."""
        self._poll_tick_counter += 1
        tick = self._poll_tick_counter
        receive_spec = get_receive_spec(self._device.profile)
        if receive_spec is None:
            _LOGGER.debug(
                "zha_infrared receiver step=poll_tick_skip entity=%s tick=%s reason=no_receive_spec",
                self.entity_id,
                tick,
            )
            return
        if self._receive_lock.locked():
            _LOGGER.debug(
                "zha_infrared receiver step=poll_tick_skip entity=%s tick=%s reason=lock_busy",
                self.entity_id,
                tick,
            )
            return
        if not self.available:
            _LOGGER.debug(
                "zha_infrared receiver step=poll_tick_skip entity=%s tick=%s reason=unavailable",
                self.entity_id,
                tick,
            )
            return

        start_monotonic = time.monotonic()
        _LOGGER.debug(
            "zha_infrared receiver step=poll_tick_start entity=%s tick=%s",
            self.entity_id,
            tick,
        )
        async with self._receive_lock:
            _LOGGER.debug(
                "zha_infrared receiver step=poll_tick_lock_acquired entity=%s tick=%s",
                self.entity_id,
                tick,
            )
            await self._async_read_receive_attribute()
        _LOGGER.debug(
            "zha_infrared receiver step=poll_tick_done entity=%s tick=%s elapsed=%.3fs",
            self.entity_id,
            tick,
            time.monotonic() - start_monotonic,
        )

    async def _async_arm_interval_tick(self, _: datetime) -> None:
        """Periodic timer for optional receiver arm command."""
        self._arm_tick_counter += 1
        tick = self._arm_tick_counter
        if self._receive_lock.locked():
            _LOGGER.debug(
                "zha_infrared receiver step=arm_tick_skip entity=%s tick=%s reason=lock_busy",
                self.entity_id,
                tick,
            )
            return
        if not self.available:
            _LOGGER.debug(
                "zha_infrared receiver step=arm_tick_skip entity=%s tick=%s reason=unavailable",
                self.entity_id,
                tick,
            )
            return
        _LOGGER.debug(
            "zha_infrared receiver step=arm_tick_start entity=%s tick=%s",
            self.entity_id,
            tick,
        )
        async with self._receive_lock:
            _LOGGER.debug(
                "zha_infrared receiver step=arm_tick_lock_acquired entity=%s tick=%s",
                self.entity_id,
                tick,
            )
            await self._async_maybe_arm_receiver(force=False)
        _LOGGER.debug(
            "zha_infrared receiver step=arm_tick_done entity=%s tick=%s",
            self.entity_id,
            tick,
        )

    async def _async_maybe_arm_receiver(
        self, *, force: bool, current_arm_value: object | None = None
    ) -> None:
        """Run optional profile-defined arm command at configured interval."""
        receive_spec = get_receive_spec(self._device.profile)
        if receive_spec is None or receive_spec.arm_command is None:
            _LOGGER.debug(
                "zha_infrared receiver step=arm_skip entity=%s reason=no_arm_command force=%s",
                self.entity_id,
                force,
            )
            return
        arm_command = receive_spec.arm_command

        cluster = get_ir_cluster(self.hass, self._device)
        if cluster is None:
            _LOGGER.debug(
                "zha_infrared receiver step=arm_skip entity=%s reason=cluster_missing",
                self.entity_id,
            )
            return

        _LOGGER.debug(
            "zha_infrared receiver step=arm_main_send entity=%s force=%s value=%s",
            self.entity_id,
            force,
            arm_command.call_value,
        )
        if await self._async_send_arm_command_with_interval(
            cluster, arm_command, arm_command.call_value
        ):
            self._arm_command_sent_monotonic = time.monotonic()
            _LOGGER.debug(
                "zha_infrared receiver step=arm_main_sent entity=%s arm_sent_monotonic=%.3f",
                self.entity_id,
                self._arm_command_sent_monotonic,
            )

    async def _async_send_arm_command_with_interval(
        self, cluster: object, arm_command: ReceiveArmCommandSpec, value: object
    ) -> bool:
        """Send arm command while enforcing minimum inter-command delay."""
        min_interval = getattr(arm_command, "min_command_interval_seconds", 2)
        if self._last_arm_transport_command_monotonic is not None:
            elapsed = time.monotonic() - self._last_arm_transport_command_monotonic
            wait_seconds = min_interval - elapsed
            if wait_seconds > 0:
                _LOGGER.debug(
                    "zha_infrared receiver step=send_arm_wait entity=%s wait=%.3fs min_interval=%ss elapsed=%.3fs",
                    self.entity_id,
                    wait_seconds,
                    min_interval,
                    elapsed,
                )
                await asyncio.sleep(wait_seconds)

        try:
            _LOGGER.debug(
                "zha_infrared receiver step=send_arm_start entity=%s command_id=%s arg=%s value=%s",
                self.entity_id,
                arm_command.call_command_id,
                arm_command.call_arg,
                value,
            )
            await cluster.command(
                arm_command.call_command_id,
                **{arm_command.call_arg: value},
                expect_reply=True,
            )
            self._last_arm_transport_command_monotonic = time.monotonic()
            _LOGGER.debug(
                "zha_infrared receiver step=send_arm_done entity=%s command_id=%s arg=%s value=%s sent_monotonic=%.3f",
                self.entity_id,
                arm_command.call_command_id,
                arm_command.call_arg,
                value,
                self._last_arm_transport_command_monotonic,
            )
            return True
        except Exception as err:
            _LOGGER.debug(
                "zha_infrared receiver step=send_arm_error entity=%s command_id=%s arg=%s value=%s error=%s",
                self.entity_id,
                arm_command.call_command_id,
                arm_command.call_arg,
                value,
                err,
            )
            return False

    async def _async_read_receive_attribute(self) -> None:
        """Read receive/arm attributes and process updates."""
        receive_spec = get_receive_spec(self._device.profile)
        if receive_spec is None:
            _LOGGER.debug(
                "zha_infrared receiver step=read_skip entity=%s reason=no_receive_spec",
                self.entity_id,
            )
            return
        arm_command = receive_spec.arm_command

        receive_cluster = get_ir_cluster(self.hass, self._device)
        if receive_cluster is None:
            _LOGGER.debug(
                "zha_infrared receiver step=read_skip entity=%s reason=cluster_missing",
                self.entity_id,
            )
            return

        attributes_to_read = [receive_spec.attribute]
        arm_state_cluster = receive_cluster
        arm_state_attribute: str | None = None
        if arm_command is not None and arm_command.reset_on_arm_value:
            arm_state_attribute = arm_command.state_attribute
            if (
                arm_command.state_cluster_id
                != self._device.profile.transport.cluster_id
            ):
                arm_state_cluster = get_cluster_by_id(
                    self.hass, self._device, arm_command.state_cluster_id
                )
                if arm_state_cluster is None:
                    _LOGGER.debug(
                        "zha_infrared receiver step=arm_state_skip entity=%s reason=state_cluster_missing cluster_id=0x%04X",
                        self.entity_id,
                        arm_command.state_cluster_id,
                    )
            elif arm_state_attribute != receive_spec.attribute:
                attributes_to_read.append(arm_state_attribute)

        _LOGGER.debug(
            "zha_infrared receiver step=read_start entity=%s attrs=%s",
            self.entity_id,
            attributes_to_read,
        )

        try:
            attrs, _ = await receive_cluster.read_attributes(
                attributes_to_read,
                allow_cache=False,
                only_cache=False,
            )
        except Exception as err:
            _LOGGER.debug(
                "zha_infrared receiver step=read_error entity=%s attrs=%s error=%s",
                self.entity_id,
                attributes_to_read,
                err,
            )
            return
        _LOGGER.debug(
            "zha_infrared receiver step=read_done entity=%s attrs_result=%s",
            self.entity_id,
            attrs,
        )

        if arm_command is not None and arm_command.reset_on_arm_value:
            arm_attr_value: object | None = None
            if arm_state_attribute is not None and arm_state_cluster is receive_cluster:
                arm_attr_value = self._get_attribute_value(
                    attrs, receive_cluster, arm_state_attribute
                )
            elif arm_state_attribute is not None and arm_state_cluster is not None:
                try:
                    arm_attrs, _ = await arm_state_cluster.read_attributes(
                        [arm_state_attribute],
                        allow_cache=False,
                        only_cache=False,
                    )
                except Exception as err:
                    _LOGGER.debug(
                        "zha_infrared receiver step=arm_state_read_error entity=%s attr=%s error=%s",
                        self.entity_id,
                        arm_state_attribute,
                        err,
                    )
                else:
                    _LOGGER.debug(
                        "zha_infrared receiver step=arm_state_read_done entity=%s attr=%s attrs_result=%s",
                        self.entity_id,
                        arm_state_attribute,
                        arm_attrs,
                    )
                    arm_attr_value = self._get_attribute_value(
                        arm_attrs, arm_state_cluster, arm_state_attribute
                    )
            if arm_attr_value is not None:
                _LOGGER.debug(
                    "zha_infrared receiver step=arm_attr_observed entity=%s arm_attr=%s value=%s",
                    self.entity_id,
                    arm_state_attribute,
                    arm_attr_value,
                )
                if self._arm_value_requires_rearm(arm_attr_value):
                    _LOGGER.debug(
                        "zha_infrared receiver step=arm_value_mismatch entity=%s value=%s action=force_rearm_in_lock",
                        self.entity_id,
                        arm_attr_value,
                    )
                    self._arm_command_sent_monotonic = None
                    await self._async_maybe_arm_receiver(
                        force=True, current_arm_value=arm_attr_value
                    )
            else:
                _LOGGER.debug(
                    "zha_infrared receiver step=arm_attr_missing entity=%s arm_attr=%s",
                    self.entity_id,
                    arm_state_attribute,
                )

        payload = self._get_attribute_value(attrs, receive_cluster, receive_spec.attribute)
        if isinstance(payload, str):
            _LOGGER.debug(
                "zha_infrared receiver step=payload_from_read entity=%s attr=%s payload_len=%s",
                self.entity_id,
                receive_spec.attribute,
                len(payload),
            )
            await self.async_process_payload(payload)
        else:
            _LOGGER.debug(
                "zha_infrared receiver step=payload_missing_or_non_string entity=%s attr=%s value=%s",
                self.entity_id,
                receive_spec.attribute,
                payload,
            )

    @callback
    def _async_on_attribute_updated(self, attr_id: int, value: object) -> None:
        """Process receive payload from attribute-report updates."""
        receive_spec = get_receive_spec(self._device.profile)
        if receive_spec is None or receive_spec.method != "cluster_attribute_report":
            return
        _LOGGER.debug(
            "zha_infrared receiver step=report_update entity=%s attr_id=%s value=%s",
            self.entity_id,
            attr_id,
            value,
        )

        cluster = get_ir_cluster(self.hass, self._device)
        if cluster is None:
            return

        arm_command = receive_spec.arm_command
        if arm_command is not None and arm_command.reset_on_arm_value:
            arm_state_attr = arm_command.state_attribute
            if arm_command.state_cluster_id != self._device.profile.transport.cluster_id:
                _LOGGER.debug(
                    "zha_infrared receiver step=report_arm_attr_skip entity=%s reason=state_cluster_not_listened cluster_id=0x%04X",
                    self.entity_id,
                    arm_command.state_cluster_id,
                )
                arm_attr_id = None
            else:
                arm_attr_id = self._resolve_receive_attribute_id(cluster, arm_state_attr)
            if arm_attr_id is not None and arm_attr_id == attr_id:
                _LOGGER.debug(
                    "zha_infrared receiver step=report_arm_attr entity=%s attr_id=%s value=%s",
                    self.entity_id,
                    attr_id,
                    value,
                )
                self._async_handle_arm_value_mismatch(value)

        expected_attr_id = self._resolve_receive_attribute_id(
            cluster, receive_spec.attribute
        )
        if expected_attr_id is None or expected_attr_id == attr_id:
            if isinstance(value, str):
                _LOGGER.debug(
                    "zha_infrared receiver step=payload_from_report entity=%s attr_id=%s payload_len=%s",
                    self.entity_id,
                    attr_id,
                    len(value),
                )
                self.hass.async_create_task(self.async_process_payload(value))
            else:
                _LOGGER.debug(
                    "zha_infrared receiver step=payload_report_non_string entity=%s attr_id=%s value=%s",
                    self.entity_id,
                    attr_id,
                    value,
                )

    def _get_attribute_value(
        self, attrs: dict[object, object], cluster: object, attribute_name: str
    ) -> object | None:
        """Extract attribute value by name with id fallback."""
        value = attrs.get(attribute_name)
        if value is not None:
            return value
        attribute_id = self._resolve_receive_attribute_id(cluster, attribute_name)
        if attribute_id is None:
            return None
        return attrs.get(attribute_id)

    def _resolve_receive_attribute_id(
        self, cluster: object, attribute_name: str
    ) -> int | None:
        """Resolve attribute id from a cluster attribute name."""
        attributes_by_name = getattr(cluster, "attributes_by_name", None)
        if not isinstance(attributes_by_name, dict):
            return None
        attribute_def = attributes_by_name.get(attribute_name)
        if attribute_def is None:
            return None
        return getattr(attribute_def, "id", None)

    @callback
    def _arm_value_requires_rearm(self, value: object) -> bool:
        """Return whether observed arm-state requires immediate re-arm."""
        receive_spec = get_receive_spec(self._device.profile)
        if receive_spec is None or receive_spec.arm_command is None:
            return False
        arm_command = receive_spec.arm_command
        target_armed_state = arm_command.state_armed_value
        if not arm_command.reset_on_arm_value or value == target_armed_state:
            _LOGGER.debug(
                "zha_infrared receiver step=arm_value_check_no_rearm entity=%s value=%s target=%s reset_on_arm_value=%s",
                self.entity_id,
                value,
                target_armed_state,
                arm_command.reset_on_arm_value,
            )
            return False
        return True

    @callback
    def _async_handle_arm_value_mismatch(self, value: object) -> None:
        """Force re-arm when arm attribute switches away from target value."""
        if not self._arm_value_requires_rearm(value):
            return
        receive_spec = get_receive_spec(self._device.profile)
        if receive_spec is None or receive_spec.arm_command is None:
            return
        arm_command = receive_spec.arm_command
        target_armed_state = arm_command.state_armed_value
        _LOGGER.debug(
            "zha_infrared receiver step=arm_value_mismatch entity=%s value=%s target=%s action=force_rearm",
            self.entity_id,
            value,
            target_armed_state,
        )
        self._arm_command_sent_monotonic = None
        self.hass.async_create_task(self._async_force_rearm(value))

    async def _async_force_rearm(self, current_arm_value: object | None) -> None:
        """Re-arm in a lock-safe way after arm-state mismatch."""
        if self._receive_lock.locked():
            _LOGGER.debug(
                "zha_infrared receiver step=force_rearm_skip entity=%s reason=lock_busy current_arm_value=%s",
                self.entity_id,
                current_arm_value,
            )
            return
        if self._subscriber_count == 0:
            _LOGGER.debug(
                "zha_infrared receiver step=force_rearm_skip entity=%s reason=no_subscribers current_arm_value=%s",
                self.entity_id,
                current_arm_value,
            )
            return
        if not self.available:
            _LOGGER.debug(
                "zha_infrared receiver step=force_rearm_skip entity=%s reason=unavailable current_arm_value=%s",
                self.entity_id,
                current_arm_value,
            )
            return
        _LOGGER.debug(
            "zha_infrared receiver step=force_rearm_start entity=%s current_arm_value=%s",
            self.entity_id,
            current_arm_value,
        )
        async with self._receive_lock:
            await self._async_maybe_arm_receiver(
                force=True, current_arm_value=current_arm_value
            )
        _LOGGER.debug(
            "zha_infrared receiver step=force_rearm_done entity=%s current_arm_value=%s",
            self.entity_id,
            current_arm_value,
        )

    async def async_process_payload(self, payload: str) -> None:
        """Decode payload and update receiver state if it is a new signal."""
        if not payload:
            _LOGGER.debug(
                "zha_infrared receiver step=process_payload_skip entity=%s reason=empty_payload",
                self.entity_id,
            )
            return
        if payload == self._last_payload:
            _LOGGER.debug(
                "zha_infrared receiver step=process_payload_skip entity=%s reason=duplicate_payload payload_len=%s",
                self.entity_id,
                len(payload),
            )
            return
        _LOGGER.debug(
            "zha_infrared receiver step=process_payload_start entity=%s payload_len=%s",
            self.entity_id,
            len(payload),
        )

        try:
            timings = decode_received_payload(self._device.profile.codec.name, payload)
        except Exception as err:
            _LOGGER.debug(
                "zha_infrared receiver step=process_payload_decode_error entity=%s codec=%s error=%s",
                self.entity_id,
                self._device.profile.codec.name,
                err,
            )
            return
        if not timings:
            self._last_payload = payload
            _LOGGER.debug(
                "zha_infrared receiver step=process_payload_no_timings entity=%s payload_len=%s",
                self.entity_id,
                len(payload),
            )
            return

        self._last_payload = payload
        receive_spec = get_receive_spec(self._device.profile)
        if (
            receive_spec is not None
            and receive_spec.arm_command is not None
            and receive_spec.arm_command.reset_interval_on_update
        ):
            self._arm_command_sent_monotonic = time.monotonic()
            _LOGGER.debug(
                "zha_infrared receiver step=process_payload_reset_arm_interval entity=%s new_arm_sent_monotonic=%.3f",
                self.entity_id,
                self._arm_command_sent_monotonic,
            )
        _LOGGER.debug(
            "zha_infrared receiver step=process_payload_emit entity=%s timings_count=%s",
            self.entity_id,
            len(timings),
        )
        self._handle_received_signal(InfraredReceivedSignal(timings=timings))
