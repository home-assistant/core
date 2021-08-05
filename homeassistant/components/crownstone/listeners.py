"""
Listeners for updating data in the Crownstone integration.

For data updates, Cloud Push is used in form of an SSE server that sends out events.
For fast device switching Local Push is used in form of UART USB with Bluetooth.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from crownstone_core.packets.serviceDataParsers.containers.AdvExternalCrownstoneState import (
    AdvExternalCrownstoneState,
)
from crownstone_core.packets.serviceDataParsers.containers.elements.AdvTypes import (
    AdvType,
)
from crownstone_core.protocol.SwitchState import SwitchState
from crownstone_sse.const import (
    EVENT_ABILITY_CHANGE,
    EVENT_ABILITY_CHANGE_DIMMING,
    EVENT_SWITCH_STATE_UPDATE,
)
from crownstone_uart import UartEventBus, UartTopics
from crownstone_uart.topics.SystemTopics import SystemTopics

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    SIG_CROWNSTONE_STATE_UPDATE,
    SIG_UART_STATE_CHANGE,
    SSE_LISTENERS,
    UART_LISTENERS,
)

if TYPE_CHECKING:
    from .entry_manager import CrownstoneEntryManager


def create_data_listeners(hass: HomeAssistant, manager: CrownstoneEntryManager) -> None:
    """Set up SSE and UART listeners."""

    @callback
    def update_crwn_state_sse(switch_state_event: Event) -> None:
        """Update the state of a Crownstone when switched from the Crownstone app."""
        sphere = manager.cloud.cloud_data.find_by_id(
            switch_state_event.data["sphere"]["id"]
        )
        if sphere is None:
            return

        updated_crownstone = sphere.crownstones.find_by_uid(
            switch_state_event.data["crownstone"]["uid"]
        )
        if updated_crownstone is None:
            return

        # only update on change.
        # HA sets the state manually when switching to assume switched, only update when necessary.
        switch_state = int(switch_state_event.data["crownstone"]["percentage"])
        if updated_crownstone.state != switch_state:
            updated_crownstone.state = switch_state

            # update the entity state
            async_dispatcher_send(hass, SIG_CROWNSTONE_STATE_UPDATE)

    @callback
    def update_ability(ability_event: Event) -> None:
        """
        Update the ability information.

        This update triggers an entry reload so the entity is re-created with the new data.
        This is because the change in supported features cannot be done during runtime.
        """
        sphere = manager.cloud.cloud_data.find_by_id(ability_event.data["sphere"]["id"])
        if sphere is None:
            return

        updated_crownstone = sphere.crownstones.find_by_uid(
            ability_event.data["stone"]["uid"]
        )
        if updated_crownstone is None:
            return

        ability_type: str = ability_event.data["ability"]["type"]
        ability_enabled: bool = ability_event.data["ability"]["enabled"]
        # only update on a change in state
        if updated_crownstone.abilities[ability_type].is_enabled != ability_enabled:
            # write the change to the crownstone entity.
            updated_crownstone.abilities[ability_type].is_enabled = ability_enabled

            if ability_event.data["subType"] == EVENT_ABILITY_CHANGE_DIMMING:
                # reload the config entry because dimming is part of supported features
                hass.async_create_task(
                    hass.config_entries.async_reload(manager.config_entry.entry_id)
                )
            else:
                # notify entity about change in state attributes
                async_dispatcher_send(hass, SIG_CROWNSTONE_STATE_UPDATE)

    def update_uart_state(data: bool | None) -> None:
        """Update the UART ready state for the power usage."""
        # update availability of power usage entities.
        async_dispatcher_send(hass, SIG_UART_STATE_CHANGE)

    def update_crwn_state_uart(data: AdvExternalCrownstoneState) -> None:
        """Update the state of a Crownstone when switched from the Crownstone app."""
        if data.type != AdvType.EXTERNAL_STATE:
            return

        updated_crownstone = None
        for sphere in manager.cloud.cloud_data:
            updated_crownstone = sphere.crownstones.find_by_uid(data.crownstoneId)

        if updated_crownstone is None:
            return

        # only update on change
        # HA sets the state manually when switching to assume switched, only update when necessary.
        if data.switchState is not None:
            # this variable is initialized as None in the lib
            updated_state = cast(SwitchState, data.switchState)
            if updated_crownstone.state != updated_state.intensity:
                updated_crownstone.state = updated_state.intensity

                # update HA state
                async_dispatcher_send(hass, SIG_CROWNSTONE_STATE_UPDATE)

    # add SSE listeners to HA eventbus
    # save unsub function for when entry removed
    manager.listeners[SSE_LISTENERS] = [
        hass.bus.async_listen(
            f"{DOMAIN}_{EVENT_SWITCH_STATE_UPDATE}", update_crwn_state_sse
        ),
        hass.bus.async_listen(f"{DOMAIN}_{EVENT_ABILITY_CHANGE}", update_ability),
    ]

    # add UART listeners to UART eventbus
    # save subscription id to unsub, UartEventBus is a singleton
    manager.listeners[UART_LISTENERS] = [
        UartEventBus.subscribe(SystemTopics.connectionEstablished, update_uart_state),
        UartEventBus.subscribe(SystemTopics.connectionClosed, update_uart_state),
        UartEventBus.subscribe(UartTopics.newDataAvailable, update_crwn_state_uart),
    ]
