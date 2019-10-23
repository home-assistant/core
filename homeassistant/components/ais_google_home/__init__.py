# -*- coding: utf-8 -*-
"""
Support for AIS Google Home

For more details about this component, please refer to the documentation at
https://ai-speaker.com
"""
import asyncio
import logging
from homeassistant.components import ais_cloud
from .const import DOMAIN
from .config_flow import configured_google_homes

aisCloud = ais_cloud.AisCloudWS()
aisCloudWS = ais_cloud.AisCloudWS()
_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup(hass, config):
    """Register the service."""

    @asyncio.coroutine
    def ask_google_home(service):
        """ask service about info"""
        yield from _process_ask_google_home(hass, service)

    hass.services.async_register(DOMAIN, "ask_google_home", ask_google_home)

    return True


@asyncio.coroutine
def _process_ask_google_home(hass, call):
    try:
        question = call.data["question"]
        ws_ret = aisCloudWS.ask_gh(question)
        m = ws_ret.text.split("---")[0]
        yield from hass.services.async_call("ais_ai_service", "say_it", {"text": m})
    except:
        yield from hass.services.async_call(
            "ais_ai_service", "say_it", {"text": "Brak odpowiedzi z Google Home"}
        )
        return


async def async_setup_entry(hass, config_entry):
    """Set up config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "sensor")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    # remove from cloud
    ws_ret = aisCloudWS.gh_ais_remove_integration()
    response = ws_ret.json()
    _LOGGER.info(response["message"])
    #
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    return True
