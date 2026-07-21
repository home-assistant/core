"""Repairs platform for the template integration."""

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import DeviceSelector


class CompositeDeviceIdRepairFlow(RepairsFlow):
    """Handler to select a device again after the linked device was split."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the fix flow."""
        # The flow manager passes {"issue_id": ...} as user_input to this step;
        # delegate so the form step can tell rendering from an (empty) submission
        return await self.async_step_select_device()

    async def async_step_select_device(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the device selection step."""
        entry = self.hass.config_entries.async_get_entry(self._entry.entry_id)
        if entry is None:
            return self.async_abort(reason="entry_removed")

        device_registry = dr.async_get(self.hass)
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input.get(CONF_DEVICE_ID)
            if device_id is None or not device_registry.async_is_composite_device_id(
                device_id
            ):
                options = {**entry.options}
                if device_id:
                    options[CONF_DEVICE_ID] = device_id
                else:
                    options.pop(CONF_DEVICE_ID, None)
                self.hass.config_entries.async_update_entry(entry, options=options)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_create_entry(data={})
            # The suggested composite device id was submitted unchanged
            errors[CONF_DEVICE_ID] = "invalid_device"

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_DEVICE_ID,
                        description={
                            "suggested_value": entry.options.get(CONF_DEVICE_ID)
                        },
                    ): DeviceSelector(),
                }
            ),
            description_placeholders={"name": entry.title},
            errors=errors,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a fix flow."""
    if (
        issue_id.startswith("composite_device_id_")
        and data is not None
        and (entry := hass.config_entries.async_get_entry(str(data["entry_id"])))
        is not None
    ):
        return CompositeDeviceIdRepairFlow(entry)
    raise HomeAssistantError(f"Unknown issue {issue_id}")
