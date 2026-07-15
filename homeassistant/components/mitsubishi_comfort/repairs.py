"""Repairs for the Mitsubishi Comfort integration."""

from ipaddress import ip_address
from typing import cast

import voluptuous as vol

from homeassistant.components.dhcp import async_discovered_service_info
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_ADDRESSES


class MissingAddressRepairFlow(RepairsFlow):
    """Collect LAN IPs for devices DHCP discovery has not resolved.

    The cloud never returns a device's LAN IP. DHCP discovery supplies it for
    devices Home Assistant can see, but not for devices on another subnet or
    VLAN — for those the user enters the IP here.
    """

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the flow for the entry that raised the issue."""
        self.entry = entry
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the fix flow.

        The repairs manager passes the flow init data ({"issue_id": ...}) as
        user_input here, so redirect to a named step that sees real form
        input only.
        """
        return await self.async_step_addresses()

    async def async_step_addresses(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Ask for the LAN IP of each device that has none."""
        stored: dict[str, str] = dict(self.entry.data.get(CONF_ADDRESSES, {}))
        device_registry = dr.async_get(self.hass)
        # Map each addressless device's formatted MAC (the address cache key)
        # to its name.
        macs: dict[str, str] = {}
        for device in dr.async_entries_for_config_entry(
            device_registry, self.entry.entry_id
        ):
            mac = next(
                (
                    conn_id
                    for conn_type, conn_id in device.connections
                    if conn_type == dr.CONNECTION_NETWORK_MAC
                ),
                None,
            )
            if mac is not None and (formatted := dr.format_mac(mac)) not in stored:
                macs[formatted] = device.name_by_user or device.name or formatted

        errors: dict[str, str] = {}
        if user_input is not None:
            updated = dict(stored)
            for mac in macs:
                value = user_input.get(mac, "").strip()
                if not value:
                    continue
                try:
                    ip_address(value)
                except ValueError:
                    errors["base"] = "invalid_ip"
                else:
                    updated[mac] = value
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={**self.entry.data, CONF_ADDRESSES: updated},
                )
                # The repairs framework deletes the issue after this step
                # returns; run the reload non-eagerly so it happens after that
                # deletion and setup can re-create the issue if devices are
                # still addressless.
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.entry.entry_id),
                    f"mitsubishi_comfort repair reload {self.entry.entry_id}",
                    eager_start=False,
                )
                return self.async_create_entry(data={})

        # Pre-fill with the submitted values on a validation error so the user
        # does not lose what they typed; otherwise suggest any IP the DHCP
        # sighting cache has picked up since setup.
        if user_input is None:
            user_input = {
                formatted: info.ip
                for info in async_discovered_service_info(self.hass)
                if (formatted := dr.format_mac(info.macaddress)) in macs
            }
        schema = vol.Schema({vol.Optional(mac): str for mac in macs})
        return self.async_show_form(
            step_id="addresses",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            # The fields are keyed (and labeled) by raw MAC, so pair each name
            # with its MAC here or the user cannot tell which field is which.
            description_placeholders={
                "devices": ", ".join(f"{name} ({mac})" for mac, name in macs.items())
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow for a missing-address issue."""
    if data is not None and (
        entry := hass.config_entries.async_get_entry(cast(str, data["entry_id"]))
    ):
        return MissingAddressRepairFlow(entry)
    return ConfirmRepairFlow()
