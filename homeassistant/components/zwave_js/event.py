"""Support for Z-Wave controls using the event platform."""
from __future__ import annotations

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value, ValueNotification

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_VALUE, DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave Event entity from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_number(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave event entity."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        if info.platform_hint == "stateless":
            entities.append(ZwaveEventEntity(config_entry, driver, info))
        else:
            raise ValueError(
                f"Discovered value with hint '{info.platform_hint} not handled"
            )
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{EVENT_DOMAIN}",
            async_add_number,
        )
    )


def _cc_and_prop(value: Value) -> str:
    """Return a string with the command class and property."""
    return f"{value.command_class}: {value.property_}"


class ZwaveEventEntity(ZWaveBaseEntity, EventEntity):
    """Representation of a Z-Wave event entity."""

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZwaveEventEntity entity."""
        super().__init__(config_entry, driver, info)

        if info.primary_value.metadata.states:
            self._attr_event_types = sorted(info.primary_value.metadata.states.values())
        else:
            self._attr_event_types = [_cc_and_prop(info.primary_value)]
        # Entity class attributes
        self._attr_name = self.generate_name(include_value_name=True)

    @callback
    def _async_handle_event(self, value_notification: ValueNotification) -> None:
        """Handle a value notification event."""
        primary_value = self.info.primary_value
        # If the notification doesn't match the value we are tracking, we can return
        if (
            value_notification.command_class != primary_value.command_class
            or value_notification.endpoint != primary_value.endpoint
            or value_notification.property_ != primary_value.property_
            or value_notification.property_key != primary_value.property_key
        ):
            return

        if primary_value.metadata.states:
            try:
                event_name = primary_value.metadata.states[
                    str(value_notification.value)
                ]
            except KeyError:
                raise KeyError(
                    f"Can't find '{value_notification.value}' in "
                    f"'{primary_value.value_id}' states"
                ) from None
        else:
            event_name = _cc_and_prop(primary_value)
        self._trigger_event(event_name, {ATTR_VALUE: value_notification.value})
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
