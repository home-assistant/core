"""Support for Haus-Bus binary sensors (Digital Inputs / Taster)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyhausbus.de.hausbus.homeassistant.proxy.Taster import Taster
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.Configuration import (
    Configuration as TasterConfiguration,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.Enabled import Enabled
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvCovered import (
    EvCovered as TasterCovered,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.EvFree import (
    EvFree as TasterFree,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.data.Status import (
    Status as TasterStatus,
)
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.EEnable import EEnable
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.EState import EState
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.MEventMask import MEventMask
from pyhausbus.de.hausbus.homeassistant.proxy.taster.params.MOptionMask import (
    MOptionMask,
)
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_ON_STATE
from .device import HausbusDevice
from .entity import HausbusEntity

if TYPE_CHECKING:
    from . import HausbusConfigEntry

import logging

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HausbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a binary sensor from a config entry."""
    gateway = config_entry.runtime_data.gateway

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "push_button_configure_events",
        {
            vol.Required("event_activation_status", default="ENABLED"): vol.In(
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

    async def async_add_binary_sensor(channel: HausbusEntity) -> None:
        """Add binary sensor entity."""
        if isinstance(channel, HausbusBinarySensor):
            async_add_entities([channel])

    gateway.register_platform_add_channel_callback(
        async_add_binary_sensor, BINARY_SENSOR_DOMAIN
    )


class HausbusBinarySensor(HausbusEntity, BinarySensorEntity):
    """Representation of a Haus-Bus binary sensor."""

    def __init__(self, channel: Taster, device: HausbusDevice) -> None:
        """Set up binary sensor."""
        super().__init__(channel, device)

        self._attr_is_on = False

    def binary_sensor_covered(self) -> None:
        """Covered binary sensor channel."""
        LOGGER.debug(
            "BinarySensor covered %s %s", self._device.device_id, self._attr_name
        )
        params = {ATTR_ON_STATE: True}
        self.async_update_callback(**params)

    def binary_sensor_free(self) -> None:
        """Freed binary sensor channel."""
        LOGGER.debug("BinarySensor free %s %s", self._device.device_id, self._attr_name)
        params = {ATTR_ON_STATE: False}
        self.async_update_callback(**params)

    def handle_event(self, data: Any) -> None:
        """Handle binary sensor events."""
        if isinstance(data, TasterCovered):
            self.binary_sensor_covered()

        elif isinstance(data, TasterFree):
            self.binary_sensor_free()

        elif isinstance(data, TasterStatus):
            if data.getState() == EState.PRESSED:
                self.binary_sensor_covered()
            else:
                self.binary_sensor_free()

        elif isinstance(data, Enabled):
            self._attr_extra_state_attributes["event_activation_status"] = (
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
                "_attr_extra_state_attributes %s", self._attr_extra_state_attributes
            )

    @callback
    def async_update_callback(self, **kwargs: Any) -> None:
        """Binary sensor state push update."""
        state_changed = False
        if ATTR_ON_STATE in kwargs and self._attr_is_on != kwargs[ATTR_ON_STATE]:
            self._attr_is_on = kwargs[ATTR_ON_STATE]
            state_changed = True

        if state_changed:
            self.schedule_update_ha_state()

    async def async_push_button_configure_events(
        self, event_activation_status: str, disabled_duration: int
    ):
        """Disables all events from this input for the given time or activates them again."""
        LOGGER.debug(
            "async_push_button_configure_events event_activation_status %s, disabled_duration %s",
            event_activation_status,
            disabled_duration,
        )

        enable = {
            "DISABLED": EEnable.FALSE,
            "ENABLED": EEnable.TRUE,
            "INVERT": EEnable.INVERT,
        }.get(event_activation_status, EEnable.TRUE)

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
            "async_push_button_set_configuration hold_timeout %s double_click_timeout %s event_button_pressed_active %s event_button_released_active %s event_button_hold_start_active %s event_button_hold_end_active %s event_button_clicked_active %s event_button_double_clicked_active %s led_feedback_active %s inverted %s debounce_time %s",
            hold_timeout,
            double_click_timeout,
            event_button_pressed_active,
            event_button_released_active,
            event_button_hold_start_active,
            event_button_hold_end_active,
            event_button_clicked_active,
            event_button_double_clicked_active,
            led_feedback_active,
            inverted,
            debounce_time,
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
