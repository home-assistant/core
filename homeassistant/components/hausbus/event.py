"""Support for events of haus-bus pushbuttons (Taster)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from pyhausbus.de.hausbus.homeassistant.proxy.Taster import Taster
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.Configuration import (
    Configuration as TasterConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.Enabled import Enabled
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvClicked import EvClicked
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import EvCovered
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvDoubleClick import (
    EvDoubleClick,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvFree import EvFree
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldEnd import EvHoldEnd
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvHoldStart import EvHoldStart
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.EEnable import EEnable
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.MEventMask import MEventMask
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.MOptionMask import (
    MOptionMask,
)

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an event entity from a config entry."""
    gateway = config_entry.runtime_data.gateway

    # Services gelten für alle HausbusLight-Entities, die die jeweilige Funktion implementieren
    platform = entity_platform.async_get_current_platform()

    # Taster Services
    platform.async_register_entity_service(
        "push_button_configure_events",
        {
            vol.Required("eventActivationStatus", default="ENABLED"): vol.In(
                ["DISABLED", "ENABLED", "INVERT"]
            ),
            vol.Optional("disabled_duration", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        "async_push_button_configure_events",
    )
    platform.async_register_entity_service(
        "push_button_set_configuration",
        {
            vol.Required("hold_timeout", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("double_click_timeout", default=50): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=255)
            ),
            vol.Required("event_button_pressed_active", default=True): vol.Boolean(),
            vol.Required("event_button_released_active", default=True): vol.Boolean(),
            vol.Required(
                "event_button_hold_start_active", default=False
            ): vol.Boolean(),
            vol.Required("event_button_hold_end_active", default=False): vol.Boolean(),
            vol.Required("event_button_clicked_active", default=False): vol.Boolean(),
            vol.Required(
                "event_button_double_clicked_active", default=False
            ): vol.Boolean(),
            vol.Required("led_feedback_active", default=True): vol.Boolean(),
            vol.Required("inverted", default=False): vol.Boolean(),
            vol.Required("debounce_time", default=40): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=254)
            ),
        },
        "async_push_button_set_configuration",
    )

    async def async_add_event(channel: HausBusEvent) -> None:
        """Add event entity."""
        async_add_entities([channel])

    gateway.register_platform_add_channel_callback(async_add_event, "EVENTS")


class HausBusEvent(HausbusEntity, EventEntity):
    """Representation of a haus-bus event entity."""

    def __init__(self, channel: Taster, device: HausbusDevice) -> None:
        """Set up event."""
        super().__init__(channel, device, "event")

        self._attr_event_types = [
            "button_pressed",
            "button_released",
            "button_clicked",
            "button_double_clicked",
            "button_hold_start",
            "button_hold_end",
        ]

    def get_hardware_status(self) -> None:
        """Request status and configuration of this channel from hardware."""
        super().get_hardware_status()
        self._channel.getEnabled()

    # @staticmethod
    # def is_relevant_event(data) -> bool:
    #    """Check if a event is relevant for an event channel."""
    #    return isinstance(data, (EvCovered, EvFree, EvHoldStart, EvHoldEnd, EvClicked, EvDoubleClick, TasterConfiguration, Enabled))

    def handle_event(self, data: Any) -> None:
        """Handle taster events from Haus-Bus."""

        if isinstance(
            data, (EvCovered, EvFree, EvHoldStart, EvHoldEnd, EvClicked, EvDoubleClick)
        ):
            eventType = {
                EvCovered: "button_pressed",
                EvFree: "button_released",
                EvHoldStart: "button_hold_start",
                EvHoldEnd: "button_hold_end",
                EvClicked: "button_clicked",
                EvDoubleClick: "button_double_clicked",
            }.get(type(data), "unknown")

            if eventType != "unknown":
                LOGGER.debug(f"sending event {eventType}")
                self._trigger_event(eventType)
                self.schedule_update_ha_state()

        elif isinstance(data, Enabled):
            self._attr_extra_state_attributes["eventActivationStatus"] = (
                "DISABLED" if data.getEnabled() == 0 else "ENABLED"
            )

        elif isinstance(data, TasterConfiguration):
            self._configuration = data

            eventMask = data.getEventMask()
            self._attr_extra_state_attributes["hold_timeout"] = data.getHoldTimeout()
            self._attr_extra_state_attributes["double_click_timeout"] = (
                data.getWaitForDoubleClickTimeout()
            )
            self._attr_extra_state_attributes["event_button_pressed_active"] = (
                eventMask.isNotifyOnCovered()
            )
            self._attr_extra_state_attributes["event_button_released_active"] = (
                eventMask.isNotifyOnFree()
            )
            self._attr_extra_state_attributes["event_button_hold_start_active"] = (
                eventMask.isNotifyOnStartHold()
            )
            self._attr_extra_state_attributes["event_button_hold_end_active"] = (
                eventMask.isNotifyOnEndHold()
            )
            self._attr_extra_state_attributes["event_button_clicked_active"] = (
                eventMask.isNotifyOnClicked()
            )
            self._attr_extra_state_attributes["event_button_double_clicked_active"] = (
                eventMask.isNotifyOnDoubleClicked()
            )
            self._attr_extra_state_attributes["led_feedback_active"] = (
                eventMask.isEnableFeedBack()
            )
            self._attr_extra_state_attributes["inverted"] = (
                data.getOptionMask().isInverted()
            )
            self._attr_extra_state_attributes["debounce_time"] = data.getDebounceTime()

            LOGGER.debug(
                f"_attr_extra_state_attributes {self._attr_extra_state_attributes}"
            )

    async def async_push_button_configure_events(
        self, eventActivationStatus: str, disabled_duration: int
    ):
        """Disables all events from this input for the given time or activates them again."""
        LOGGER.debug(
            f"async_push_button_configure_events eventActivationStatus {eventActivationStatus}, disabled_duration {disabled_duration}"
        )

        enable = {
            "DISABLED": EEnable.FALSE,
            "ENABLED": EEnable.TRUE,
            "INVERT": EEnable.INVERT,
        }.get(eventActivationStatus, EEnable.TRUE)

        self._channel.enableEvents(enable, disabled_duration)

    async def async_push_button_set_configuration(
        self,
        hold_timeout: int,
        double_click_timeout: int,
        event_button_pressed_active: bool,
        event_button_released_active: bool,
        event_button_hold_start_active: bool,
        event_button_hold_end_active: bool,
        event_button_clicked_active: bool,
        event_button_double_clicked_active: bool,
        led_feedback_active: bool,
        inverted: bool,
        debounce_time: int,
    ):
        """Sets configuration for this input."""
        LOGGER.debug(
            f"async_push_button_set_configuration hold_timeout {hold_timeout}, double_click_timeout {double_click_timeout}, event_button_pressed_active {event_button_pressed_active}, event_button_released_active {event_button_released_active}, event_button_hold_start_active {event_button_hold_start_active}, event_button_hold_end_active {event_button_hold_end_active}, event_button_clicked_active {event_button_clicked_active}, event_button_double_clicked_active {event_button_double_clicked_active}, led_feedback_active {led_feedback_active}, inverted {inverted}, debounce_time {debounce_time}"
        )

        if not await self.ensure_configuration():
            raise HomeAssistantError(
                "Configuration could not be read. Please repeat command."
            )

        eventMask = MEventMask()
        eventMask.setNotifyOnCovered(event_button_pressed_active)
        eventMask.setNotifyOnFree(event_button_released_active)
        eventMask.setNotifyOnClicked(event_button_clicked_active)
        eventMask.setNotifyOnDoubleClicked(event_button_double_clicked_active)
        eventMask.setNotifyOnStartHold(event_button_hold_start_active)
        eventMask.setNotifyOnEndHold(event_button_hold_end_active)
        eventMask.setEnableFeedBack(led_feedback_active)
        eventMask.setReserved1(self._configuration.getEventMask().isReserved1())

        optionMask = MOptionMask()
        optionMask.setPulldown(self._configuration.getOptionMask().isPulldown())
        optionMask.setInverted(inverted)

        self._channel.setConfiguration(
            hold_timeout, double_click_timeout, eventMask, optionMask, debounce_time
        )
        self._channel.getConfiguration()
