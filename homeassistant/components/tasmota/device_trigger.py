"""Provides device automations for Tasmota."""
from __future__ import annotations

from collections.abc import Callable
import logging

import attr
from hatasmota.models import DiscoveryHashType
from hatasmota.trigger import TasmotaTrigger, TasmotaTriggerConfig
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, TASMOTA_EVENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_UPDATED, clear_discovery_hash

_LOGGER = logging.getLogger(__name__)

CONF_DISCOVERY_ID = "discovery_id"
CONF_SUBTYPE = "subtype"
DEVICE = "device"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DEVICE,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DISCOVERY_ID): str,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
    }
)

DEVICE_TRIGGERS = "tasmota_device_triggers"


@attr.s(slots=True)
class TriggerInstance:
    """Attached trigger settings."""

    action: TriggerActionType = attr.ib()
    trigger_info: TriggerInfo = attr.ib()
    trigger: Trigger = attr.ib()
    remove: CALLBACK_TYPE | None = attr.ib(default=None)

    async def async_attach_trigger(self) -> None:
        """Attach event trigger."""
        assert self.trigger.tasmota_trigger is not None
        event_config = {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: TASMOTA_EVENT,
            event_trigger.CONF_EVENT_DATA: {
                "mac": self.trigger.tasmota_trigger.cfg.mac,
                "source": self.trigger.tasmota_trigger.cfg.subtype,
                "event": self.trigger.tasmota_trigger.cfg.event,
            },
        }

        event_config = event_trigger.TRIGGER_SCHEMA(event_config)
        if self.remove:
            self.remove()
        # Note: No lock needed, event_trigger.async_attach_trigger
        # is an synchronous function
        self.remove = await event_trigger.async_attach_trigger(
            self.trigger.hass,
            event_config,
            self.action,
            self.trigger_info,
            platform_type="device",
        )


@attr.s(slots=True)
class Trigger:
    """Device trigger settings."""

    device_id: str = attr.ib()
    discovery_hash: DiscoveryHashType | None = attr.ib()
    hass: HomeAssistant = attr.ib()
    remove_update_signal: Callable[[], None] | None = attr.ib()
    subtype: str = attr.ib()
    tasmota_trigger: TasmotaTrigger | None = attr.ib()
    type: str = attr.ib()
    trigger_instances: list[TriggerInstance] = attr.ib(factory=list)

    async def add_trigger(
        self, action: TriggerActionType, trigger_info: TriggerInfo
    ) -> Callable[[], None]:
        """Add Tasmota trigger."""
        instance = TriggerInstance(action, trigger_info, self)
        self.trigger_instances.append(instance)

        if self.tasmota_trigger is not None:
            # If we know about the trigger, set it up
            await instance.async_attach_trigger()

        @callback
        def async_remove() -> None:
            """Remove trigger."""
            if instance not in self.trigger_instances:
                raise HomeAssistantError("Can't remove trigger twice")

            if instance.remove:
                instance.remove()
            self.trigger_instances.remove(instance)

        return async_remove

    def detach_trigger(self) -> None:
        """Remove Tasmota device trigger."""
        # Mark trigger as unknown
        self.tasmota_trigger = None

        # Unsubscribe if this trigger is in use
        for trig in self.trigger_instances:
            if trig.remove:
                trig.remove()
                trig.remove = None

    async def arm_tasmota_trigger(self) -> None:
        """Arm Tasmota trigger: subscribe to MQTT topics and fire events."""

        @callback
        def _on_trigger() -> None:
            assert self.tasmota_trigger is not None
            data = {
                "mac": self.tasmota_trigger.cfg.mac,
                "source": self.tasmota_trigger.cfg.subtype,
                "event": self.tasmota_trigger.cfg.event,
            }
            self.hass.bus.async_fire(
                TASMOTA_EVENT,
                data,
            )

        assert self.tasmota_trigger is not None
        self.tasmota_trigger.set_on_trigger_callback(_on_trigger)
        await self.tasmota_trigger.subscribe_topics()

    async def set_tasmota_trigger(
        self, tasmota_trigger: TasmotaTrigger, remove_update_signal: Callable[[], None]
    ) -> None:
        """Set Tasmota trigger."""
        await self.update_tasmota_trigger(tasmota_trigger.cfg, remove_update_signal)
        self.tasmota_trigger = tasmota_trigger

        for trig in self.trigger_instances:
            await trig.async_attach_trigger()

    async def update_tasmota_trigger(
        self,
        tasmota_trigger_cfg: TasmotaTriggerConfig,
        remove_update_signal: Callable[[], None],
    ) -> None:
        """Update Tasmota trigger."""
        self.remove_update_signal = remove_update_signal
        self.type = tasmota_trigger_cfg.type
        self.subtype = tasmota_trigger_cfg.subtype


async def async_setup_trigger(
    hass: HomeAssistant,
    tasmota_trigger: TasmotaTrigger,
    config_entry: ConfigEntry,
    discovery_hash: DiscoveryHashType,
) -> None:
    """Set up a discovered Tasmota device trigger."""
    discovery_id = tasmota_trigger.cfg.trigger_id
    remove_update_signal: Callable[[], None] | None = None
    _LOGGER.debug(
        "Discovered trigger with ID: %s '%s'", discovery_id, tasmota_trigger.cfg
    )

    async def discovery_update(trigger_config: TasmotaTriggerConfig) -> None:
        """Handle discovery update."""
        _LOGGER.debug(
            "Got update for trigger with hash: %s '%s'", discovery_hash, trigger_config
        )
        device_triggers: dict[str, Trigger] = hass.data[DEVICE_TRIGGERS]
        if not trigger_config.is_active:
            # Empty trigger_config: Remove trigger
            _LOGGER.debug("Removing trigger: %s", discovery_hash)
            if discovery_id in device_triggers:
                device_trigger = device_triggers[discovery_id]
                assert device_trigger.tasmota_trigger
                await device_trigger.tasmota_trigger.unsubscribe_topics()
                device_trigger.detach_trigger()
                clear_discovery_hash(hass, discovery_hash)
                if remove_update_signal is not None:
                    remove_update_signal()
            return

        device_trigger = device_triggers[discovery_id]
        assert device_trigger.tasmota_trigger
        if device_trigger.tasmota_trigger.config_same(trigger_config):
            # Unchanged payload: Ignore to avoid unnecessary unsubscribe / subscribe
            _LOGGER.debug("Ignoring unchanged update for: %s", discovery_hash)
            return

        # Non-empty, changed trigger_config: Update trigger
        _LOGGER.debug("Updating trigger: %s", discovery_hash)
        device_trigger.tasmota_trigger.config_update(trigger_config)
        assert remove_update_signal
        await device_trigger.update_tasmota_trigger(
            trigger_config, remove_update_signal
        )
        await device_trigger.arm_tasmota_trigger()
        return

    remove_update_signal = async_dispatcher_connect(
        hass, TASMOTA_DISCOVERY_ENTITY_UPDATED.format(*discovery_hash), discovery_update
    )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        connections={(CONNECTION_NETWORK_MAC, tasmota_trigger.cfg.mac)},
    )

    if device is None:
        return

    if DEVICE_TRIGGERS not in hass.data:
        hass.data[DEVICE_TRIGGERS] = {}
    device_triggers: dict[str, Trigger] = hass.data[DEVICE_TRIGGERS]
    if discovery_id not in device_triggers:
        device_trigger = Trigger(
            hass=hass,
            device_id=device.id,
            discovery_hash=discovery_hash,
            subtype=tasmota_trigger.cfg.subtype,
            tasmota_trigger=tasmota_trigger,
            type=tasmota_trigger.cfg.type,
            remove_update_signal=remove_update_signal,
        )
        device_triggers[discovery_id] = device_trigger
    else:
        # This Tasmota trigger is wanted by device trigger(s), set them up
        device_trigger = device_triggers[discovery_id]
        await device_trigger.set_tasmota_trigger(tasmota_trigger, remove_update_signal)
    await device_trigger.arm_tasmota_trigger()


async def async_remove_triggers(hass: HomeAssistant, device_id: str) -> None:
    """Cleanup any device triggers for a Tasmota device."""
    triggers = await async_get_triggers(hass, device_id)

    if not triggers:
        return
    device_triggers: dict[str, Trigger] = hass.data[DEVICE_TRIGGERS]
    for trig in triggers:
        device_trigger = device_triggers.pop(trig[CONF_DISCOVERY_ID])
        if device_trigger:
            discovery_hash = device_trigger.discovery_hash

            assert device_trigger.tasmota_trigger
            await device_trigger.tasmota_trigger.unsubscribe_topics()
            device_trigger.detach_trigger()
            clear_discovery_hash(hass, discovery_hash)
            assert device_trigger.remove_update_signal
            device_trigger.remove_update_signal()


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for a Tasmota device."""
    triggers: list[dict[str, str]] = []

    if DEVICE_TRIGGERS not in hass.data:
        return triggers

    device_triggers: dict[str, Trigger] = hass.data[DEVICE_TRIGGERS]
    for discovery_id, trig in device_triggers.items():
        if trig.device_id != device_id or trig.tasmota_trigger is None:
            continue

        trigger = {
            "platform": "device",
            "domain": "tasmota",
            "device_id": device_id,
            "type": trig.type,
            "subtype": trig.subtype,
            "discovery_id": discovery_id,
        }
        triggers.append(trigger)

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a device trigger."""
    if DEVICE_TRIGGERS not in hass.data:
        hass.data[DEVICE_TRIGGERS] = {}
    device_triggers: dict[str, Trigger] = hass.data[DEVICE_TRIGGERS]
    device_id = config[CONF_DEVICE_ID]
    discovery_id = config[CONF_DISCOVERY_ID]

    if discovery_id not in device_triggers:
        # The trigger has not (yet) been discovered, prepare it for later
        device_triggers[discovery_id] = Trigger(
            hass=hass,
            device_id=device_id,
            discovery_hash=None,
            remove_update_signal=None,
            type=config[CONF_TYPE],
            subtype=config[CONF_SUBTYPE],
            tasmota_trigger=None,
        )
    trigger: Trigger = device_triggers[discovery_id]
    return await trigger.add_trigger(action, trigger_info)
