"""Provides device automations for MQTT."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

import attr
import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import debug_info, trigger as mqtt_trigger
from .config import MQTT_BASE_SCHEMA
from .const import (
    ATTR_DISCOVERY_HASH,
    CONF_ENCODING,
    CONF_PAYLOAD,
    CONF_QOS,
    CONF_TOPIC,
    DOMAIN,
)
from .discovery import MQTTDiscoveryPayload, clear_discovery_hash
from .mixins import (
    MQTT_ENTITY_DEVICE_INFO_SCHEMA,
    MqttDiscoveryDeviceUpdate,
    send_discovery_done,
    update_device,
)
from .models import DATA_MQTT

_LOGGER = logging.getLogger(__name__)

CONF_AUTOMATION_TYPE = "automation_type"
CONF_DISCOVERY_ID = "discovery_id"
CONF_SUBTYPE = "subtype"
DEFAULT_ENCODING = "utf-8"
DEVICE = "device"

MQTT_TRIGGER_BASE = {
    # Trigger when MQTT message is received
    CONF_PLATFORM: DEVICE,
    CONF_DOMAIN: DOMAIN,
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DEVICE,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_DEVICE_ID): str,
        # The use of CONF_DISCOVERY_ID was deprecated in HA Core 2024.2.
        # By default, a MQTT device trigger now will be referenced by
        # device_id, type and subtype instead.
        vol.Optional(CONF_DISCOVERY_ID): str,
        vol.Required(CONF_TYPE): cv.string,
        vol.Required(CONF_SUBTYPE): cv.string,
    },
)

TRIGGER_DISCOVERY_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_AUTOMATION_TYPE): str,
        vol.Required(CONF_DEVICE): MQTT_ENTITY_DEVICE_INFO_SCHEMA,
        vol.Optional(CONF_PAYLOAD, default=None): vol.Any(None, cv.string),
        vol.Required(CONF_SUBTYPE): cv.string,
        vol.Required(CONF_TOPIC): cv.string,
        vol.Required(CONF_TYPE): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE, default=None): vol.Any(None, cv.string),
    },
    extra=vol.REMOVE_EXTRA,
)

LOG_NAME = "Device trigger"


@attr.s(slots=True)
class TriggerInstance:
    """Attached trigger settings."""

    action: TriggerActionType = attr.ib()
    trigger_info: TriggerInfo = attr.ib()
    trigger: Trigger = attr.ib()
    remove: CALLBACK_TYPE | None = attr.ib(default=None)

    async def async_attach_trigger(self) -> None:
        """Attach MQTT trigger."""
        mqtt_config: dict[str, Any] = {
            CONF_PLATFORM: DOMAIN,
            CONF_TOPIC: self.trigger.topic,
            CONF_ENCODING: DEFAULT_ENCODING,
            CONF_QOS: self.trigger.qos,
        }
        if self.trigger.payload:
            mqtt_config[CONF_PAYLOAD] = self.trigger.payload
        if self.trigger.value_template:
            mqtt_config[CONF_VALUE_TEMPLATE] = self.trigger.value_template
        mqtt_config = mqtt_trigger.TRIGGER_SCHEMA(mqtt_config)

        if self.remove:
            self.remove()
        self.remove = await mqtt_trigger.async_attach_trigger(
            self.trigger.hass,
            mqtt_config,
            self.action,
            self.trigger_info,
        )


@attr.s(slots=True)
class Trigger:
    """Device trigger settings."""

    device_id: str = attr.ib()
    discovery_data: DiscoveryInfoType | None = attr.ib()
    discovery_id: str | None = attr.ib()
    hass: HomeAssistant = attr.ib()
    payload: str | None = attr.ib()
    qos: int | None = attr.ib()
    subtype: str = attr.ib()
    topic: str | None = attr.ib()
    type: str = attr.ib()
    value_template: str | None = attr.ib()
    trigger_instances: list[TriggerInstance] = attr.ib(factory=list)

    async def add_trigger(
        self, action: TriggerActionType, trigger_info: TriggerInfo
    ) -> Callable[[], None]:
        """Add MQTT trigger."""
        instance = TriggerInstance(action, trigger_info, self)
        self.trigger_instances.append(instance)

        if self.topic is not None:
            # If we know about the trigger, subscribe to MQTT topic
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

    async def update_trigger(self, config: ConfigType) -> None:
        """Update MQTT device trigger."""
        self.type = config[CONF_TYPE]
        self.subtype = config[CONF_SUBTYPE]
        self.payload = config[CONF_PAYLOAD]
        self.qos = config[CONF_QOS]
        topic_changed = self.topic != config[CONF_TOPIC]
        self.topic = config[CONF_TOPIC]
        self.value_template = config[CONF_VALUE_TEMPLATE]

        # Unsubscribe+subscribe if this trigger is in use and topic has changed
        # If topic is same unsubscribe+subscribe will execute in the wrong order
        # because unsubscribe is done with help of async_create_task
        if topic_changed:
            for trig in self.trigger_instances:
                await trig.async_attach_trigger()

    def detach_trigger(self) -> None:
        """Remove MQTT device trigger."""
        # Mark trigger as unknown
        self.topic = None

        # Unsubscribe if this trigger is in use
        for trig in self.trigger_instances:
            if trig.remove:
                trig.remove()
                trig.remove = None


class MqttDeviceTrigger(MqttDiscoveryDeviceUpdate):
    """Setup a MQTT device trigger with auto discovery."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        device_id: str,
        discovery_data: DiscoveryInfoType,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._config = config
        self._config_entry = config_entry
        self.device_id = device_id
        self.discovery_data = discovery_data
        self.hass = hass
        self._mqtt_data = hass.data[DATA_MQTT]
        self.trigger_id = f"{device_id}_{config[CONF_TYPE]}_{config[CONF_SUBTYPE]}"

        MqttDiscoveryDeviceUpdate.__init__(
            self,
            hass,
            discovery_data,
            device_id,
            config_entry,
            LOG_NAME,
        )

    async def async_setup(self) -> None:
        """Initialize the device trigger."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        discovery_id = discovery_hash[1]
        # The use of CONF_DISCOVERY_ID was deprecated in HA Core 2024.2.
        # To make sure old automation keep working we determine the trigger_id
        # based on the discovery_id if it is set.
        for trigger_id, trigger in self._mqtt_data.device_triggers.items():
            if trigger.discovery_id == discovery_id:
                self.trigger_id = trigger_id
                break
        if self.trigger_id not in self._mqtt_data.device_triggers:
            self._mqtt_data.device_triggers[self.trigger_id] = Trigger(
                hass=self.hass,
                device_id=self.device_id,
                discovery_data=self.discovery_data,
                discovery_id=discovery_id,
                type=self._config[CONF_TYPE],
                subtype=self._config[CONF_SUBTYPE],
                topic=self._config[CONF_TOPIC],
                payload=self._config[CONF_PAYLOAD],
                qos=self._config[CONF_QOS],
                value_template=self._config[CONF_VALUE_TEMPLATE],
            )
        else:
            await self._mqtt_data.device_triggers[self.trigger_id].update_trigger(
                self._config
            )
        debug_info.add_trigger_discovery_data(
            self.hass, discovery_hash, self.discovery_data, self.device_id
        )

    async def async_update(self, discovery_data: MQTTDiscoveryPayload) -> None:
        """Handle MQTT device trigger discovery updates."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        debug_info.update_trigger_discovery_data(
            self.hass, discovery_hash, discovery_data
        )
        config = TRIGGER_DISCOVERY_SCHEMA(discovery_data)
        new_trigger_id = f"{self.device_id}_{config[CONF_TYPE]}_{config[CONF_SUBTYPE]}"
        if new_trigger_id != self.trigger_id:
            mqtt_data = self.hass.data[DATA_MQTT]
            if new_trigger_id in mqtt_data.device_triggers:
                _LOGGER.error(
                    "Cannot update device trigger %s due to an existing duplicate "
                    "device trigger with the same device_id, "
                    "type and subtype. Got: %s",
                    discovery_hash,
                    config,
                )
                return
            # Update trigger_id based index after update of type or subtype
            mqtt_data.device_triggers[new_trigger_id] = mqtt_data.device_triggers.pop(
                self.trigger_id
            )
            self.trigger_id = new_trigger_id

        update_device(self.hass, self._config_entry, config)
        device_trigger: Trigger = self._mqtt_data.device_triggers[self.trigger_id]
        await device_trigger.update_trigger(config)

    async def async_tear_down(self) -> None:
        """Cleanup device trigger."""
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        if self.trigger_id in self._mqtt_data.device_triggers:
            _LOGGER.info("Removing trigger: %s", discovery_hash)
            trigger: Trigger = self._mqtt_data.device_triggers[self.trigger_id]
            trigger.discovery_data = None
            trigger.detach_trigger()
            debug_info.remove_trigger_discovery_data(self.hass, discovery_hash)


async def async_setup_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType,
) -> None:
    """Set up the MQTT device trigger."""
    config = TRIGGER_DISCOVERY_SCHEMA(config)

    # We update the device based on the trigger config to obtain the device_id.
    # In all cases the setup will lead to device entry to be created or updated.
    # If the trigger is a duplicate, trigger creation will be cancelled but we allow
    # the device data to be updated to not add additional complexity to the code.
    device_id = update_device(hass, config_entry, config)
    discovery_id = discovery_data[ATTR_DISCOVERY_HASH][1]
    trigger_type = config[CONF_TYPE]
    trigger_subtype = config[CONF_SUBTYPE]
    trigger_id = f"{device_id}_{trigger_type}_{trigger_subtype}"
    mqtt_data = hass.data[DATA_MQTT]
    if (
        trigger_id in mqtt_data.device_triggers
        and mqtt_data.device_triggers[trigger_id].discovery_data is not None
    ):
        _LOGGER.error(
            "Config for device trigger %s conflicts with existing "
            "device trigger, cannot set up trigger, got: %s",
            discovery_id,
            config,
        )
        send_discovery_done(hass, discovery_data)
        clear_discovery_hash(hass, discovery_data[ATTR_DISCOVERY_HASH])
        return None

    if TYPE_CHECKING:
        assert isinstance(device_id, str)
    mqtt_device_trigger = MqttDeviceTrigger(
        hass, config, device_id, discovery_data, config_entry
    )
    await mqtt_device_trigger.async_setup()
    send_discovery_done(hass, discovery_data)


async def async_removed_from_device(hass: HomeAssistant, device_id: str) -> None:
    """Handle Mqtt removed from a device."""
    mqtt_data = hass.data[DATA_MQTT]
    triggers = await async_get_triggers(hass, device_id)
    for trig in triggers:
        trigger_id = f"{device_id}_{trig[CONF_TYPE]}_{trig[CONF_SUBTYPE]}"
        if trigger_id in mqtt_data.device_triggers:
            device_trigger = mqtt_data.device_triggers.pop(trigger_id)
            device_trigger.detach_trigger()
            discovery_data = device_trigger.discovery_data
            if TYPE_CHECKING:
                assert discovery_data is not None
            discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
            debug_info.remove_trigger_discovery_data(hass, discovery_hash)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for MQTT devices."""
    mqtt_data = hass.data[DATA_MQTT]

    if not mqtt_data.device_triggers:
        return []

    return [
        {
            **MQTT_TRIGGER_BASE,
            "device_id": device_id,
            "type": trig.type,
            "subtype": trig.subtype,
        }
        for trig in mqtt_data.device_triggers.values()
        if trig.device_id == device_id and trig.topic is not None
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_id: str | None = None
    mqtt_data = hass.data[DATA_MQTT]
    device_id = config[CONF_DEVICE_ID]

    # The use of CONF_DISCOVERY_ID was deprecated in HA Core 2024.2.
    # In case CONF_DISCOVERY_ID is still used in an automation,
    # we reference the device trigger by discovery_id instead of
    # referencing it by device_id, type and subtype, which is the default.
    discovery_id: str | None = config.get(CONF_DISCOVERY_ID)
    if discovery_id is not None:
        for trig_id, trig in mqtt_data.device_triggers.items():
            if trig.discovery_id == discovery_id:
                trigger_id = trig_id
                break

    # Reference the device trigger by device_id, type and subtype.
    if trigger_id is None:
        trigger_type = config[CONF_TYPE]
        trigger_subtype = config[CONF_SUBTYPE]
        trigger_id = f"{device_id}_{trigger_type}_{trigger_subtype}"

    if trigger_id not in mqtt_data.device_triggers:
        mqtt_data.device_triggers[trigger_id] = Trigger(
            hass=hass,
            device_id=device_id,
            discovery_data=None,
            discovery_id=discovery_id,
            type=config[CONF_TYPE],
            subtype=config[CONF_SUBTYPE],
            topic=None,
            payload=None,
            qos=None,
            value_template=None,
        )

    return await mqtt_data.device_triggers[trigger_id].add_trigger(action, trigger_info)
