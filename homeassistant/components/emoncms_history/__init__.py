"""Support for sending data to Emoncms."""

from datetime import datetime, timedelta
from functools import partial
import logging

import aiohttp
from pyemoncms import EmoncmsClient
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_WHITELIST,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, state as state_helper
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "emoncms_history"
CONF_INPUTNODE = "inputnode"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_URL): cv.string,
                vol.Required(CONF_INPUTNODE): cv.positive_int,
                vol.Required(CONF_WHITELIST): cv.entity_ids,
                vol.Optional(CONF_SCAN_INTERVAL, default=30): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_send_to_emoncms(
    hass: HomeAssistant,
    emoncms_client: EmoncmsClient,
    whitelist: list[str],
    node: str | int,
    _: datetime,
) -> None:
    """Send data to Emoncms."""
    payload_dict = {}

    for entity_id in whitelist:
        state = hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE):
            continue
        try:
            payload_dict[entity_id] = state_helper.state_as_number(state)
        except ValueError:
            continue

    if payload_dict:
        try:
            await emoncms_client.async_input_post(data=payload_dict, node=node)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Network error when sending data to Emoncms: %s", err)
        except ValueError as err:
            _LOGGER.warning("Value error when preparing data for Emoncms: %s", err)
        else:
            _LOGGER.debug("Sent data to Emoncms: %s", payload_dict)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Emoncms history component."""
    conf = config[DOMAIN]
    whitelist = conf.get(CONF_WHITELIST)
    input_node = str(conf.get(CONF_INPUTNODE))

    emoncms_client = EmoncmsClient(
        url=conf.get(CONF_URL),
        api_key=conf.get(CONF_API_KEY),
        session=async_get_clientsession(hass),
    )
    async_track_time_interval(
        hass,
        partial(async_send_to_emoncms, hass, emoncms_client, whitelist, input_node),
        timedelta(seconds=conf.get(CONF_SCAN_INTERVAL)),
    )

    return True
