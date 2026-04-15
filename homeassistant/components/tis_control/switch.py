"""Switch platform for TIS Control."""

from __future__ import annotations

from typing import Any, TypedDict

from TISApi.api import TISApi
from TISApi.components.switch.base_switch import TISAPISwitch

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TISConfigEntry
from .const import DOMAIN


class SwitchDescription(TypedDict):
    """Normalized switch payload."""

    switch_name: str | None
    channel_number: int
    device_id: list[int]
    is_protected: bool
    gateway: str | None


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
        # Extract the channel number from the nested data structure.
        # The raw data looks like: "channels": [{"Output": 1}].
        # 1. appliance["channels"][0]: Get the first dictionary in the list -> {"Output": 1}.
        # 2. .values(): Get the dictionary's values -> dict_values([1]).
        # 3. list(...)[0]: Convert to a list and get the first element -> 1.

        # Validate that channels is a non-empty list.
        channels = appliance.get("channels")
        if not isinstance(channels, list) or not channels:
            continue

        # Validate that the first channel entry is a non-empty dict.
        first_channel = channels[0]
        if not isinstance(first_channel, dict) or not first_channel:
            continue

        # Safely get the first value from the channel dict.
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

        # Create a new, clean dictionary with a standardized format.
        result.append(
            SwitchDescription(
                switch_name=appliance.get("name"),
                channel_number=channel_number,
                device_id=device_id,
                is_protected=appliance.get("is_protected", False),
                gateway=appliance.get("gateway"),
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
        self.device_api = device_api

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
    def _handle_update(self) -> None:
        """Handle state updates from the TISAPISwitch object."""
        self._attr_is_on = self.device_api.is_on
        self._attr_available = self.device_api.available
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to Home Assistant."""
        # Register the HASS update method as the callback
        self.device_api.register_callback(self._handle_update)

        # Request an initial state update from the device.
        await self.device_api.request_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Attempt to turn the switch on and wait for the result.
        result = await self.device_api.turn_switch_on()

        if result:
            self._attr_is_on = True
            self._attr_available = True
        else:
            # If no ack was received, the device is likely offline.
            self._attr_available = False

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Send the 'off' packet and wait for an acknowledgement.
        result = await self.device_api.turn_switch_off()

        if result:
            self._attr_is_on = False
            self._attr_available = True
        else:
            # If no ack was received, the device is likely offline.
            self._attr_available = False

        self.async_write_ha_state()
