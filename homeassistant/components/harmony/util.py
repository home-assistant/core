"""The Logitech Harmony Hub integration utils."""
from aioharmony.harmonyapi import HarmonyAPI as HarmonyClient


def find_unique_id_for_remote(harmony: HarmonyClient):
    """Find the unique id for both websocket and xmpp clients."""
    websocket_unique_id = harmony.hub_config.info.get("activeRemoteId")
    if websocket_unique_id is not None:
        return websocket_unique_id

    # fallback to the xmpp unique id if websocket is not available
    return harmony.config["global"]["timeStampHash"].split(";")[-1]
