"""Support for Z-Wave controls using the event platform."""

from dataclasses import dataclass
from typing import Any

from zwave_js_server.const.command_class.battery import BatteryReplacementStatus
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.notification import BatteryNotification
from zwave_js_server.model.value import Value, ValueNotification

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_URGENCY, ATTR_VALUE, DOMAIN
from .entity import NewZwaveDiscoveryInfo, ZWaveBaseEntity
from .helpers import get_device_info, get_valueless_base_unique_id
from .models import (
    NewZWaveDiscoverySchema,
    ZwaveJSConfigEntry,
    ZWaveValueDiscoverySchema,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ValueNotificationZWaveJSEntityDescription(EventEntityDescription):
    """Represent a Z-Wave JS event entity description."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZwaveJSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave Event entity from Config Entry."""
    client = config_entry.runtime_data.client

    @callback
    def async_add_event(info: NewZwaveDiscoveryInfo) -> None:
        """Add Z-Wave event entity."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = [
            info.entity_class(config_entry, driver, info)
        ]
        async_add_entities(entities)

    @callback
    def async_add_battery_low_event_entity(node: ZwaveNode) -> None:
        """Add a battery low event entity for the given node."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        async_add_entities([ZWaveBatteryLowEventEntity(driver, node)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{EVENT_DOMAIN}",
            async_add_event,
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_battery_low_event_entity",
            async_add_battery_low_event_entity,
        )
    )


def _cc_and_label(value: Value) -> str:
    """Return a string with the command class and label."""
    label = value.metadata.label
    if label:
        label = label.lower()
    return f"{value.command_class_name.capitalize()} {label}".strip()


class ZwaveEventEntity(ZWaveBaseEntity, EventEntity):
    """Representation of a Z-Wave event entity."""

    def __init__(
        self,
        config_entry: ZwaveJSConfigEntry,
        driver: Driver,
        info: NewZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZwaveEventEntity entity."""
        super().__init__(config_entry, driver, info)
        value = self.value = info.primary_value
        self.states: dict[int, str] = {}

        if states := value.metadata.states:
            self._attr_event_types = sorted(states.values())
            self.states = {int(k): v for k, v in states.items()}
        else:
            self._attr_event_types = [_cc_and_label(value)]
        # Entity class attributes
        self._attr_name = self.generate_name(include_value_name=True)

    @callback
    def _async_handle_event(self, value_notification: ValueNotification) -> None:
        """Handle a value notification event."""
        # If the notification doesn't match the value we are tracking, we can return
        value = self.value
        if (
            value_notification.command_class != value.command_class
            or value_notification.endpoint != value.endpoint
            or value_notification.property_ != value.property_
            or value_notification.property_key != value.property_key
            or (notification_value := value_notification.value) is None
        ):
            return
        event_name = self.states.get(notification_value, _cc_and_label(value))
        self._trigger_event(event_name, {ATTR_VALUE: notification_value})
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.info.node.on(
                "value notification",
                lambda event: self._async_handle_event(event["value_notification"]),
            )
        )


class ZWaveBatteryLowEventEntity(EventEntity):
    """Representation of a Battery CC battery low event entity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_event_types = [
        BatteryReplacementStatus.SOON.name.lower(),
        BatteryReplacementStatus.NOW.name.lower(),
    ]
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "battery_low"

    def __init__(self, driver: Driver, node: ZwaveNode) -> None:
        """Initialize a Battery low event entity."""
        self.node = node
        self._base_unique_id = get_valueless_base_unique_id(driver, node)
        self._attr_unique_id = f"{self._base_unique_id}.battery_low"
        # device may not be precreated in main handler yet
        self._attr_device_info = get_device_info(driver, node)

    @callback
    def _async_handle_notification(self, event: dict[str, Any]) -> None:
        """Handle a node battery low notification."""
        if not isinstance(
            notification := event.get("notification"), BatteryNotification
        ):
            return
        urgency = notification.urgency
        if urgency is BatteryReplacementStatus.NO:
            return
        self._trigger_event(urgency.name.lower(), {ATTR_URGENCY: urgency.value})
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._base_unique_id}_remove_entity",
                self.async_remove,
            )
        )
        self.async_on_remove(
            self.node.on("notification", self._async_handle_notification)
        )


DISCOVERY_SCHEMAS: list[NewZWaveDiscoverySchema] = [
    NewZWaveDiscoverySchema(
        platform=Platform.EVENT,
        primary_value=ZWaveValueDiscoverySchema(
            stateful=False,
        ),
        entity_description=ValueNotificationZWaveJSEntityDescription(
            key="value_notification",
        ),
        entity_class=ZwaveEventEntity,
    ),
]
