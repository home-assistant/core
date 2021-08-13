"""
Listeners for updating data in the Crownstone integration.

For data updates, Cloud Push is used in form of an SSE server that sends out events.
For fast device switching Local Push is used in form of UART USB with Bluetooth.
"""
from __future__ import annotations

from functools import partial
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
from crownstone_sse.events import AbilityChangeEvent, SwitchStateUpdateEvent
from crownstone_uart import UartEventBus, UartTopics
from crownstone_uart.topics.SystemTopics import SystemTopics

from homeassistant.core import Event, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send

from .const import (
    DOMAIN,
    SIG_CROWNSTONE_STATE_UPDATE,
    SIG_UART_STATE_CHANGE,
    SSE_LISTENERS,
    UART_LISTENERS,
)

if TYPE_CHECKING:
    from .entry_manager import CrownstoneEntryManager


@callback
def update_crwn_state_sse(manager: CrownstoneEntryManager, ha_event: Event) -> None:
    """Update the state of a Crownstone when switched externally."""
    switch_event = SwitchStateUpdateEvent(ha_event.data)
    try:
        updated_crownstone = manager.cloud.get_crownstone_by_id(switch_event.cloud_id)
    except KeyError:
        return

    # only update on change.
    if updated_crownstone.state != switch_event.switch_state:
        updated_crownstone.state = switch_event.switch_state
        async_dispatcher_send(manager.hass, SIG_CROWNSTONE_STATE_UPDATE)


@callback
def update_crwn_ability(manager: CrownstoneEntryManager, ha_event: Event) -> None:
    """Update the ability information of a Crownstone."""
    ability_event = AbilityChangeEvent(ha_event.data)
    try:
        updated_crownstone = manager.cloud.get_crownstone_by_id(ability_event.cloud_id)
    except KeyError:
        return

    ability_type = ability_event.ability_type
    ability_enabled = ability_event.ability_enabled
    # only update on a change in state
    if updated_crownstone.abilities[ability_type].is_enabled != ability_enabled:
        # write the change to the crownstone entity.
        updated_crownstone.abilities[ability_type].is_enabled = ability_enabled

        if ability_event.sub_type == EVENT_ABILITY_CHANGE_DIMMING:
            # reload the config entry because dimming is part of supported features
            manager.hass.async_create_task(
                manager.hass.config_entries.async_reload(manager.config_entry.entry_id)
            )
        else:
            async_dispatcher_send(manager.hass, SIG_CROWNSTONE_STATE_UPDATE)


def update_uart_state(manager: CrownstoneEntryManager, data: bool | None) -> None:
    """Update the uart ready state for entities that use USB."""
    # update availability of power usage entities.
    dispatcher_send(manager.hass, SIG_UART_STATE_CHANGE)


def update_crwn_state_uart(
    manager: CrownstoneEntryManager, data: AdvExternalCrownstoneState
) -> None:
    """Update the state of a Crownstone when switched externally."""
    if data.type != AdvType.EXTERNAL_STATE:
        return
    updated_crownstone = None
    for sphere in manager.cloud.cloud_data:
        if sphere.cloud_id == manager.usb_sphere_id:
            updated_crownstone = sphere.crownstones.find_by_uid(data.crownstoneId)
    if updated_crownstone is None:
        return

    # only update on change
    if data.switchState is not None:
        # this variable is initialized as None in the lib
        updated_state = cast(SwitchState, data.switchState)
        if updated_crownstone.state != updated_state.intensity:
            updated_crownstone.state = updated_state.intensity

            dispatcher_send(manager.hass, SIG_CROWNSTONE_STATE_UPDATE)


def setup_sse_listeners(manager: CrownstoneEntryManager) -> None:
    """Set up SSE listeners."""
    # save unsub function for when entry removed
    manager.listeners[SSE_LISTENERS] = [
        manager.hass.bus.async_listen(
            f"{DOMAIN}_{EVENT_SWITCH_STATE_UPDATE}",
            partial(update_crwn_state_sse, manager),
        ),
        manager.hass.bus.async_listen(
            f"{DOMAIN}_{EVENT_ABILITY_CHANGE}",
            partial(update_crwn_ability, manager),
        ),
    ]


def setup_uart_listeners(manager: CrownstoneEntryManager) -> None:
    """Set up UART listeners."""
    # save subscription id to unsub
    manager.listeners[UART_LISTENERS] = [
        UartEventBus.subscribe(
            SystemTopics.connectionEstablished,
            partial(update_uart_state, manager),
        ),
        UartEventBus.subscribe(
            SystemTopics.connectionClosed,
            partial(update_uart_state, manager),
        ),
        UartEventBus.subscribe(
            UartTopics.newDataAvailable,
            partial(update_crwn_state_uart, manager),
        ),
    ]
