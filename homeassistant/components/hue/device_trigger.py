"""Provides device automations for Philips Hue events."""

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .v1.device_trigger import (
    async_attach_trigger as async_attach_trigger_v1,
    async_get_triggers as async_get_triggers_v1,
    async_validate_trigger_config as async_validate_trigger_config_v1,
)
from .v2.device_trigger import (
    async_attach_trigger as async_attach_trigger_v2,
    async_get_triggers as async_get_triggers_v2,
    async_validate_trigger_config as async_validate_trigger_config_v2,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo

    from .bridge import HueConfigEntry

LOGGER = logging.getLogger(__name__)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    device_id = config[CONF_DEVICE_ID]
    dev_reg = dr.async_get(hass)
    if (
        device_entry := dev_reg.async_get(device_id, include_child_devices=False)
    ) is None:
        raise InvalidDeviceAutomationConfig(f"Device ID {device_id} is not valid")
    entry = _async_get_hue_entry(hass, device_entry)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        # Happens at startup: the device_automation framework only calls this
        # validator once the owning entry is loaded, so stay lenient here.
        return config
    bridge = entry.runtime_data
    bridge_device = _async_get_bridge_device(hass, device_entry, entry)
    if bridge.api_version == 1:
        return await async_validate_trigger_config_v1(bridge, bridge_device, config)
    return await async_validate_trigger_config_v2(bridge, bridge_device, config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    device_id = config[CONF_DEVICE_ID]
    dev_reg = dr.async_get(hass)
    if (
        device_entry := dev_reg.async_get(device_id, include_child_devices=False)
    ) is None:
        raise InvalidDeviceAutomationConfig(f"Device ID {device_id} is not valid")
    if (entry := _async_get_hue_entry(hass, device_entry)) is None:
        raise InvalidDeviceAutomationConfig(
            f"Device ID {device_id} is not found on any Hue bridge"
        )
    # Unlike async_get_triggers, the bridge must be given the device it knows
    # itself: a v1 bridge matches its events by the split device's id.
    bridge_device = _async_get_bridge_device(hass, device_entry, entry)

    if entry.state is not ConfigEntryState.LOADED:
        # The bridge is still setting up when automations are attached at startup.
        return _async_attach_on_entry_load(
            hass, entry, bridge_device, config, action, trigger_info
        )

    return await _async_attach_bridge_trigger(
        entry, bridge_device, config, action, trigger_info
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Get device triggers for given (hass) device id."""
    dev_reg = dr.async_get(hass)
    # A restored composite is passed to the bridge as-is, so the returned triggers
    # echo the requested device id (async_get_device_automations keys its results
    # by that id).
    if (
        device_entry := dev_reg.async_get(device_id, include_child_devices=False)
    ) is None:
        raise ValueError(f"Device ID {device_id} is not valid")
    entry = _async_get_hue_entry(hass, device_entry)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        return []
    bridge = entry.runtime_data
    if bridge.api_version == 1:
        return async_get_triggers_v1(bridge, device_entry)
    return async_get_triggers_v2(bridge, device_entry)


@callback
def _async_get_hue_entry(
    hass: HomeAssistant, device_entry: dr.DeviceEntry
) -> HueConfigEntry | None:
    """Return the Hue config entry the device belongs to, preferring a loaded one.

    A device is connected to a single Hue bridge at a time, so a device belonging
    to several Hue config entries is pathological. A loaded entry is preferred
    anyway, in case the bridge of one of them was decommissioned and its entry
    only disabled.
    """
    if not device_entry.is_composite_device:
        entry = hass.config_entries.async_get_entry(device_entry.config_entry_id)
        if entry is None or entry.domain != DOMAIN:
            return None
        return entry
    entries = [
        entry
        for entry_id in device_entry.config_entries
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None
        and entry.domain == DOMAIN
    ]
    for entry in entries:
        if entry.state is ConfigEntryState.LOADED:
            return entry
    # Fall back to a not loaded entry, attaching a trigger waits for it to load
    return entries[0] if entries else None


@callback
def _async_get_bridge_device(
    hass: HomeAssistant, device_entry: dr.DeviceEntry, entry: HueConfigEntry
) -> dr.DeviceEntry:
    """Return the device as known by the bridge of the given config entry.

    A bridge only knows the split device belonging to its own config entry, not
    the restored composite spanning several config entries.
    """
    if not device_entry.is_composite_device:
        return device_entry
    dev_reg = dr.async_get(hass)
    return next(
        (
            split_device
            for split_device in dev_reg.async_get_devices_for_composite_device_id(
                device_entry.id
            )
            if split_device.config_entry_id == entry.entry_id
        ),
        device_entry,
    )


async def _async_attach_bridge_trigger(
    entry: HueConfigEntry,
    device_entry: dr.DeviceEntry,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach the trigger to the bridge of a loaded config entry."""
    bridge = entry.runtime_data
    if bridge.api_version == 1:
        return await async_attach_trigger_v1(
            bridge, device_entry, config, action, trigger_info
        )
    return await async_attach_trigger_v2(
        bridge, device_entry, config, action, trigger_info
    )


@callback
def _async_attach_on_entry_load(
    hass: HomeAssistant,
    entry: HueConfigEntry,
    device_entry: dr.DeviceEntry,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach the trigger as soon as the given config entry is loaded.

    The returned callback detaches the trigger and is safe to call while the
    config entry is still loading.
    """
    remove_trigger: CALLBACK_TYPE | None = None
    attach_scheduled = False

    async def _async_attach() -> None:
        nonlocal remove_trigger
        try:
            remove_trigger = await _async_attach_bridge_trigger(
                entry, device_entry, config, action, trigger_info
            )
        except InvalidDeviceAutomationConfig as err:
            LOGGER.error(
                "Got error '%s' when setting up triggers for %s",
                err,
                trigger_info["name"],
            )

    @callback
    def _handle_entry_state_change() -> None:
        nonlocal attach_scheduled
        # Unsubscribing here would mutate the list this callback is iterated from,
        # so the subscription is kept until the trigger is detached.
        if attach_scheduled or entry.state is not ConfigEntryState.LOADED:
            return
        attach_scheduled = True
        hass.async_create_task(_async_attach())

    unsub_state_change = entry.async_on_state_change(_handle_entry_state_change)

    @callback
    def _remove() -> None:
        unsub_state_change()
        if remove_trigger is not None:
            remove_trigger()

    return _remove
