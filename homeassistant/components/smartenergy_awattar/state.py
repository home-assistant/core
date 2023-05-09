"""Awattar state management."""

from awattar_api.awattar_api import AwattarApi

from .const import API, UNSUB_OPTIONS_UPDATE_LISTENER


def init_state(url: str) -> dict:
    """Initialize the state with Awattar API."""

    return {API: AwattarApi(url), UNSUB_OPTIONS_UPDATE_LISTENER: {}}
