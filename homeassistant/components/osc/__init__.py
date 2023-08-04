"""The OSC (Open Sound Control) integration."""
import logging

from pythonosc.udp_client import SimpleUDPClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Define the service schema
SERVICE_OSC_SEND_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.string,
        vol.Required("value"): cv.string,
        vol.Required("data_type"): vol.In(["float", "int"]),
    }
)


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    hass.data.setdefault(DOMAIN, {})

    def handle_send_osc(call: ServiceCall):
        """Handle the service call."""
        entity_id = call.data.get("entity_id")
        value = call.data.get("value")
        data_type = call.data.get("data_type")

        if entity_id is None or value is None or data_type is None:
            _LOGGER.error("Missing required parameters in the service call")
            return

        # Convert the value to the appropriate data type
        if data_type == "int":
            try:
                value = int(value)
            except ValueError:
                _LOGGER.error(f"Cannot convert value to int: {value}")
                return
        elif data_type == "float":
            try:
                value = float(value)
            except ValueError:
                _LOGGER.error(f"Cannot convert value to float: {value}")
                return

        # Extract the OSC address from the entity_id and replace '_' with '/'
        osc_address = "/" + entity_id.split(".")[1].replace("_", "/")

        # Get the host, port, and OSC address from the config entry of the specified entity
        for entry_osc_address, config in hass.data[DOMAIN].items():
            if entry_osc_address == osc_address:
                host = config["host"]
                port = config["port"]
                # Store the value in the hass.data dictionary
                hass.data[DOMAIN][entry_osc_address]["value"] = value
                break
        else:
            _LOGGER.error(f"Entity not found: {entity_id}")
            return

        client = SimpleUDPClient(host, port)

        try:
            client.send_message(osc_address, value)
            _LOGGER.info(
                f"Sent OSC message: Address: {osc_address}, Value: {value}, Destination: {host}:{port}"
            )
        except OSError as e:
            _LOGGER.error(f"Failed to send OSC message: {e}")

    # Register the service with the defined schema
    hass.services.register(
        DOMAIN, "osc_send", handle_send_osc, schema=SERVICE_OSC_SEND_SCHEMA
    )

    # Return boolean to indicate that initialization was successful.
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OSC (Open Sound Control) from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Store the host, port, device name, and OSC address for later use
    osc_address = entry.data["osc_address"]
    hass.data[DOMAIN][osc_address] = {
        "host": entry.data["host"],
        "port": int(entry.data["port"]),
        "osc_address": osc_address,
        # Initialize 'value' to None
        "value": None,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.data["osc_address"])

    return unload_ok
