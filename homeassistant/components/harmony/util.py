"""The Logitech Harmony Hub integration utils."""
import aioharmony.exceptions as harmony_exceptions
from aioharmony.harmonyapi import HarmonyAPI

from homeassistant.const import CONF_HOST, CONF_NAME

from .const import DOMAIN


def find_unique_id_for_remote(harmony: HarmonyAPI):
    """Find the unique id for both websocket and xmpp clients."""
    websocket_unique_id = harmony.hub_config.info.get("activeRemoteId")
    if websocket_unique_id is not None:
        return websocket_unique_id

    # fallback to the xmpp unique id if websocket is not available
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
