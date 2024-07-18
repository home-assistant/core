"""Provides helpers for Z-Wave JS device automations."""

from __future__ import annotations

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.model.value import ConfigurationValue

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DATA_CLIENT, DOMAIN

NODE_STATUSES = ["asleep", "awake", "dead", "alive"]

CONF_SUBTYPE = "subtype"
CONF_VALUE_ID = "value_id"

VALUE_ID_REGEX = r"([0-9]+-[0-9]+-[0-9]+-).+"


def generate_config_parameter_subtype(config_value: ConfigurationValue) -> str:
    """Generate the config parameter name used in a device automation subtype."""
    parameter = str(config_value.property_)
    if config_value.property_key:
        # Property keys for config values are always an int
        assert isinstance(config_value.property_key, int)
        parameter = (
            f"{parameter}[{hex(config_value.property_key)}] on endpoint "
            f"{config_value.endpoint}"
        )

    return (
        f"{parameter} ({config_value.property_name}) on endpoint "
        f"{config_value.endpoint}"
    )


@callback
def async_bypass_dynamic_config_validation(hass: HomeAssistant, device_id: str) -> bool:
    """Return whether device's config entries are not loaded."""
    dev_reg = dr.async_get(hass)
    if (device := dev_reg.async_get(device_id)) is None:
        raise ValueError(f"Device {device_id} not found")
    entry = next(
        (
            config_entry
            for config_entry in hass.config_entries.async_entries(DOMAIN)
            if config_entry.entry_id in device.config_entries
            and config_entry.state == ConfigEntryState.LOADED
        ),
        None,
    )
    if not entry:
        return True

    # The driver may not be ready when the config entry is loaded.
    client: ZwaveClient = entry.runtime_data[DATA_CLIENT]
    return client.driver is None
