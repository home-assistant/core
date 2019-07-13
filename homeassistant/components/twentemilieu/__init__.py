"""Support for Twente Milieu."""
from datetime import timedelta
import logging

from twentemilieu import TwenteMilieu
import voluptuous as vol

from homeassistant.components.twentemilieu.const import (
    CONF_HOUSE_LETTER,
    CONF_HOUSE_NUMBER,
    CONF_POST_CODE,
    DATA_UPDATE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

SCAN_INTERVAL = timedelta(seconds=86400)

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema({vol.Optional(CONF_ID): cv.string})


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Twente Milieu components."""
    return True


async def async_setup_entry(
        hass: HomeAssistantType, entry: ConfigEntry
) -> bool:
    """Set up Twente Milieu from a config entry."""
    session = async_get_clientsession(hass)
    twentemilieu = TwenteMilieu(
        post_code=entry.data[CONF_POST_CODE],
        house_number=entry.data[CONF_HOUSE_NUMBER],
        house_letter=entry.data[CONF_HOUSE_LETTER],
        session=session,
    )

    unique_id = entry.data[CONF_ID]
    hass.data.setdefault(DOMAIN, {})[unique_id] = twentemilieu

    async def update(call) -> None:
        """Service call to manually update the data."""
        unique_id = call.data.get(CONF_ID, None)
        if unique_id is not None:
            twentemilieu = hass.data[DOMAIN].get(unique_id, None)
            if twentemilieu is not None:
                await twentemilieu.update()
                async_dispatcher_send(hass, DATA_UPDATE, unique_id)
        else:
            for twentemilieu in hass.data[DOMAIN].values():
                unique_id = await twentemilieu.unique_id()
                await twentemilieu.update()
                async_dispatcher_send(hass, DATA_UPDATE, unique_id)

    hass.services.async_register(
        DOMAIN, "update", update, schema=SERVICE_SCHEMA
    )

    async_track_time_interval(hass, update, SCAN_INTERVAL)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(
        hass: HomeAssistantType, entry: ConfigType
) -> bool:
    """Unload Twente Milieu config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")

    del hass.data[DOMAIN]

    return True
