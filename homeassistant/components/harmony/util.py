"""The Logitech Harmony Hub integration utils."""
import aioharmony.exceptions as harmony_exceptions
from aioharmony.harmonyapi import HarmonyAPI

from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN


def find_unique_id_for_remote(harmony: HarmonyAPI):
    """Find the unique id for both websocket and xmpp clients."""
    if harmony.hub_id is not None:
        return str(harmony.hub_id)

    # fallback timeStampHash if Hub ID is not available
    return harmony.config["global"]["timeStampHash"].split(";")[-1]


def find_best_name_for_remote(data: dict, harmony: HarmonyAPI):
    """Find the best name from config or fallback to the remote."""
    # As a last resort we get the name from the harmony client
    # in the event a name was not provided.  harmony.name is
    # usually the ip address but it can be an empty string.
    if CONF_NAME not in data or data[CONF_NAME] is None or data[CONF_NAME] == "":
        return harmony.name

    return data[CONF_NAME]


async def get_harmony_client_if_available(ip_address: str):
    """Connect to a harmony hub and fetch info."""
    harmony = HarmonyAPI(ip_address=ip_address)

    try:
        if not await harmony.connect():
            await harmony.close()
            return None
    except harmony_exceptions.TimeOut:
        return None

    await harmony.close()

    return harmony


def find_matching_config_entries_for_host(hass, host):
    """Search existing config entries for one matching the host."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_HOST] == host:
            return entry
    return None


def list_names_from_hublist(hub_list):
    """Extract the name key value from a hub list of names."""
    if not hub_list:
        return []
    return [
        element["name"]
        for element in hub_list
        if element.get("name") and element.get("id") != -1
    ]
