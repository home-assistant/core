"""Switch platform for TIS Control."""

from datetime import datetime, timedelta
import logging
from typing import Any, TypedDict, override

from TISApi.api import TISApi
from TISApi.components.switch.base_switch import TISAPISwitch

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import TISConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Feedback types that prove the device answered (or was reported offline) and
# therefore must be reflected in the entity availability.
_AVAILABILITY_FEEDBACK_TYPES = ("control_response", "update_response", "offline_device")

# How often an unavailable switch asks its device for a status update. The
# answer (if the device is back) restores availability through the normal
# feedback path, so recovery does not require reloading the config entry.
RECOVERY_PROBE_INTERVAL = timedelta(seconds=30)


class SwitchDescription(TypedDict):
    """Normalized switch payload."""

    switch_name: str | None
    channel_number: int
    device_id: list[int]
    is_protected: bool
    gateway: str


async def async_get_switches(tis_api: TISApi) -> list[SwitchDescription]:
    """Fetch switches from TIS API and normalize to a list of TypedDicts.

    Having this helper makes the setup code easier to test and keeps the
    API parsing logic in one place.
    """
    # Call the API to get all entities that are classified as switches.
    raw = await tis_api.get_entities(platform=Platform.SWITCH)

    # If the API returns no switches, return an empty list immediately.
    if not raw:
        return []

    # Prepare a list to hold the formatted switch data.
    result: list[SwitchDescription] = []

    # Iterate through the raw data for each switch appliance returned by the API.
    for appliance in raw:
        if not isinstance(appliance, dict):
            continue

        # Extract the channel number from the nested data structure.
        # The raw data typically looks like: "channels": [{"Output": 1}].
        # Use the first channel entry, prefer the "Output" field when present,
        # and fall back to the first available value for older payload shapes.

        # Validate that channels is a non-empty list.
        channels = appliance.get("channels")
        if not isinstance(channels, list) or not channels:
            continue

        # Validate that the first channel entry is a non-empty dict.
        first_channel = channels[0]
        if not isinstance(first_channel, dict) or not first_channel:
            continue

        # Safely get the value from the channel dict, preferring 'Output'.
        channel_value = first_channel.get("Output")
        if channel_value is None:
            channel_value = next(iter(first_channel.values()), None)

        if channel_value is None:
            continue

        try:
            channel_number = int(channel_value)
        except TypeError, ValueError:
            # Skip appliances with non-numeric channel values.
            continue

        # Validate device_id to ensure it's a list that can be converted to ints
        raw_device_id = appliance.get("device_id")
        if not isinstance(raw_device_id, list):
            continue

        try:
            device_id = [int(i) for i in raw_device_id]
        except TypeError, ValueError:
            continue

        # Skip invalid switch payloads without a usable device identifier.
        if not device_id:
            continue

        # Create a new, clean dictionary with a standardized format.
        result.append(
            SwitchDescription(
                switch_name=appliance.get("name"),
                channel_number=channel_number,
                device_id=device_id,
                is_protected=bool(appliance.get("is_protected", False)),
                gateway=appliance.get("gateway") or "",
            )
        )

    # Return the final list of formatted switches.
    return result


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TISConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TIS switches from a config entry."""

    # Retrieve the API instance that was created in the main `__init__.py`.
    tis_api: TISApi = entry.runtime_data.tis_api

    # Fetch all available switches from the TIS gateway.
    switch_dicts = await async_get_switches(tis_api)
    if not switch_dicts:
        return

    # Create an entity object for each switch found and add them to Home Assistant.
    async_add_entities(
        [TISSwitch(entry.entry_id, TISAPISwitch(tis_api, **sd)) for sd in switch_dicts],
        update_before_add=True,
    )


class TISSwitch(SwitchEntity):
    """Represents a TIS switch entity in Home Assistant."""

    _attr_has_entity_name = True

    def __init__(self, entry_id: str, device_api: TISAPISwitch) -> None:
        """Initialize the switch entity."""
        self._entry_id = entry_id
        self.device_api = device_api

        # Unsubscribe handle for the recovery probe; None while no probe runs.
        self._unsub_recovery_probe: CALLBACK_TYPE | None = None

        dev_id_str = "_".join(str(i) for i in self.device_api.device_id)
        gateway = getattr(self.device_api, "gateway", "")
        identifier_str = f"{gateway}_{dev_id_str}" if gateway else dev_id_str

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{identifier_str}")},
            name=f"TIS Device {dev_id_str}",
            manufacturer="TIS Control",
        )

        if self.device_api.name:
            self._attr_name = self.device_api.name
        else:
            self._attr_name = f"Channel {self.device_api.channel_number}"

        self._attr_unique_id = f"{entry_id}_{self.device_api.unique_id}"
        self._attr_should_poll = False
        self._attr_available = self.device_api.available

        self._attr_is_on = self.device_api.is_on

    @callback
    def _set_available(self, available: bool) -> None:
        """Set the availability and start/stop the recovery probe accordingly.

        Every availability change goes through here so the probe is always
        running while (and only while) the entity is unavailable.
        """
        self._attr_available = available
        self._update_recovery_probe()

    @callback
    def _update_recovery_probe(self) -> None:
        """Run the recovery probe while the entity is unavailable."""
        # `hass` is not set before the entity is added (e.g. during the initial
        # `update_before_add` refresh); the probe is re-evaluated once added.
        if self.hass is None:
            return

        if self._attr_available:
            self._stop_recovery_probe()
        elif self._unsub_recovery_probe is None:
            self._unsub_recovery_probe = async_track_time_interval(
                self.hass,
                self._async_probe_device,
                RECOVERY_PROBE_INTERVAL,
                cancel_on_shutdown=True,
            )

    @callback
    def _stop_recovery_probe(self) -> None:
        """Stop the recovery probe if it is running."""
        if self._unsub_recovery_probe is not None:
            self._unsub_recovery_probe()
            self._unsub_recovery_probe = None

    async def _async_probe_device(self, _now: datetime) -> None:
        """Ask an unavailable device for its status.

        If the device is back, its update response is routed through
        `_handle_event`, which restores the availability and stops the probe.
        """
        try:
            await self.device_api.request_update()
        except OSError as err:
            _LOGGER.debug("Recovery probe for %s failed: %s", self.entity_id, err)

    @callback
    def _handle_update(self) -> None:
        """Handle state updates from the TISAPISwitch object."""
        self._attr_is_on = self.device_api.is_on
        self._set_available(self.device_api.available)
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to Home Assistant."""
        # Register the HASS update method as the callback and store the unsubscribe hook.
        # Home Assistant will automatically call `unsubscribe()` when the entity is removed.
        self.async_on_remove(self.device_api.register_callback(self._handle_update))

        # Listen for events from the TIS API via the dispatcher
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{DOMAIN}_{self._entry_id}_event", self._handle_event
            )
        )

        # Make sure the probe never outlives the entity, and start it right away
        # if the entity was already unavailable when it got added.
        self.async_on_remove(self._stop_recovery_probe)
        self._update_recovery_probe()

    @callback
    def _handle_event(self, event_data: dict[str, Any]) -> None:
        """Handle incoming events from the dispatcher."""
        # Check if the event is for this device. Several gateways can share the
        # same UDP port and reuse the same bus addresses, so the event must match
        # both the gateway it came from and the device ID.
        if (
            event_data.get("gateway") == self.device_api.gateway
            and event_data.get("device_id") == self.device_api.device_id
        ):
            self.device_api.process_update(event_data)

            # The wrapper only invokes its callback when its own state or
            # availability changes. A failed action marks only this entity as
            # unavailable, so valid feedback with an unchanged on/off state would
            # never restore it. Re-sync the availability from the wrapper after
            # every valid feedback so both stay synchronized.
            if (
                event_data.get("feedback_type") in _AVAILABILITY_FEEDBACK_TYPES
                and self._attr_available != self.device_api.available
            ):
                self._set_available(self.device_api.available)
                self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity state."""
        await self.device_api.request_update()
        self._attr_is_on = self.device_api.is_on
        self._set_available(self.device_api.available)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Attempt to turn the switch on and wait for the result.
        result = await self.device_api.turn_switch_on()

        # None means the command was debounced or superseded by a newer one and
        # was never sent, so it is a no-op rather than a failed acknowledgement.
        if result is None:
            return

        if result:
            self._attr_is_on = True
            self._set_available(True)
        else:
            # If no ack was received, the device is likely offline. The recovery
            # probe started by `_set_available` keeps checking until it answers.
            self._set_available(False)

        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Send the 'off' packet and wait for an acknowledgement.
        result = await self.device_api.turn_switch_off()

        # None means the command was debounced or superseded by a newer one and
        # was never sent, so it is a no-op rather than a failed acknowledgement.
        if result is None:
            return

        if result:
            self._attr_is_on = False
            self._set_available(True)
        else:
            # If no ack was received, the device is likely offline. The recovery
            # probe started by `_set_available` keeps checking until it answers.
            self._set_available(False)

        self.async_write_ha_state()
