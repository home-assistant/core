"""Describe Z-Wave JS logbook events."""
from __future__ import annotations

from collections.abc import Callable

from zwave_js_server.const import CommandClass

from homeassistant.components.logbook.const import (
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import Event, HomeAssistant, callback
import homeassistant.helpers.device_registry as dr

from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_COMMAND_CLASS_NAME,
    ATTR_DATA_TYPE,
    ATTR_DIRECTION,
    ATTR_EVENT_LABEL,
    ATTR_EVENT_TYPE,
    ATTR_LABEL,
    ATTR_VALUE,
    DOMAIN,
    ZWAVE_JS_NOTIFICATION_EVENT,
    ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
)


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""
    dev_reg = dr.async_get(hass)

    @callback
    def async_describe_zwave_js_notification_event(
        event: Event,
    ) -> dict[str, str]:
        """Describe Z-Wave JS notification event."""
        device = dev_reg.devices[event.data[ATTR_DEVICE_ID]]
        # Z-Wave JS devices always have a name
        device_name = device.name_by_user or device.name
        assert device_name

        command_class = event.data[ATTR_COMMAND_CLASS]
        command_class_name = event.data[ATTR_COMMAND_CLASS_NAME]

        data: dict[str, str] = {LOGBOOK_ENTRY_NAME: device_name}
        prefix = f"fired {command_class_name} CC 'notification' event"

        if command_class == CommandClass.NOTIFICATION:
            label = event.data[ATTR_LABEL]
            event_label = event.data[ATTR_EVENT_LABEL]
            return {
                **data,
                LOGBOOK_ENTRY_MESSAGE: f"{prefix} '{label}': '{event_label}'",
            }

        if command_class == CommandClass.ENTRY_CONTROL:
            event_type = event.data[ATTR_EVENT_TYPE]
            data_type = event.data[ATTR_DATA_TYPE]
            return {
                **data,
                LOGBOOK_ENTRY_MESSAGE: (
                    f"{prefix} for event type '{event_type}' with data type "
                    f"'{data_type}'"
                ),
            }

        if command_class == CommandClass.SWITCH_MULTILEVEL:
            event_type = event.data[ATTR_EVENT_TYPE]
            direction = event.data[ATTR_DIRECTION]
            return {
                **data,
                LOGBOOK_ENTRY_MESSAGE: (
                    f"{prefix} for event type '{event_type}': '{direction}'"
                ),
            }

        return {**data, LOGBOOK_ENTRY_MESSAGE: prefix}

    @callback
    def async_describe_zwave_js_value_notification_event(
        event: Event,
    ) -> dict[str, str]:
        """Describe Z-Wave JS value notification event."""
        device = dev_reg.devices[event.data[ATTR_DEVICE_ID]]
        # Z-Wave JS devices always have a name
        device_name = device.name_by_user or device.name
        assert device_name

        command_class = event.data[ATTR_COMMAND_CLASS_NAME]
        label = event.data[ATTR_LABEL]
        value = event.data[ATTR_VALUE]

        return {
            LOGBOOK_ENTRY_NAME: device_name,
            LOGBOOK_ENTRY_MESSAGE: (
                f"fired {command_class} CC 'value notification' event for '{label}': "
                f"'{value}'"
            ),
        }

    async_describe_event(
        DOMAIN, ZWAVE_JS_NOTIFICATION_EVENT, async_describe_zwave_js_notification_event
    )
    async_describe_event(
        DOMAIN,
        ZWAVE_JS_VALUE_NOTIFICATION_EVENT,
        async_describe_zwave_js_value_notification_event,
    )
