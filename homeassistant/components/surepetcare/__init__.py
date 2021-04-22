"""The surepetcare integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from surepy import Surepy
from surepy.enums import EntityType, LockState
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCK_STATE,
    CONF_FEEDERS,
    CONF_FELAQUAS,
    CONF_FLAPS,
    CONF_PETS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SPC,
    SURE_API_TIMEOUT,
    SURE_IDS,
    TOPIC_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]
SCAN_INTERVAL = timedelta(minutes=3)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_FEEDERS, default=[]): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_FLAPS, default=[]): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_FELAQUAS, default=[]): vol.All(
                    cv.ensure_list, [cv.positive_int]
                ),
                vol.Optional(CONF_PETS): vol.All(cv.ensure_list, [cv.positive_int]),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the openSenseMap air quality platform."""

    conf = config[DOMAIN]

    ids: dict[str, list[int]] = {
        EntityType.PET.name: conf[CONF_PETS],
        EntityType.PET_FLAP.name: conf[CONF_FLAPS],
        EntityType.FEEDER.name: conf[CONF_FEEDERS],
        EntityType.FELAQUA.name: conf[CONF_FELAQUAS],
    }

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][SURE_IDS] = ids

    try:
        surepy = Surepy(
            conf[CONF_USERNAME],
            conf[CONF_PASSWORD],
            auth_token=None,
            api_timeout=SURE_API_TIMEOUT,
            session=async_get_clientsession(hass),
        )

    except SurePetcareAuthenticationError:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong credentials!")
        return False
    except SurePetcareError as error:
        _LOGGER.error("Unable to connect to surepetcare.io: Wrong %s!", error)
        return False

    spc = SurePetcareAPI(hass, surepy, ids)
    hass.data[DOMAIN][SPC] = spc

    await spc.async_update()

    async_track_time_interval(hass, spc.async_update, SCAN_INTERVAL)

    # load platforms
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("binary_sensor", DOMAIN, {}, config)
    )
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform("sensor", DOMAIN, {}, config)
    )

    async def handle_set_lock_state(call):
        """Call when setting the lock state."""
        await spc.set_lock_state(call.data[ATTR_FLAP_ID], call.data[ATTR_LOCK_STATE])
        await spc.async_update()

    lock_state_service_schema = vol.Schema(
        {
            vol.Required(ATTR_FLAP_ID): vol.All(
                cv.positive_int, vol.In(conf[CONF_FLAPS])
            ),
            vol.Required(ATTR_LOCK_STATE): vol.All(
                cv.string,
                vol.Lower,
                vol.In(
                    [
                        LockState.UNLOCKED.name.lower(),
                        LockState.LOCKED_IN.name.lower(),
                        LockState.LOCKED_OUT.name.lower(),
                        LockState.LOCKED_ALL.name.lower(),
                    ]
                ),
            ),
        }
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LOCK_STATE,
        handle_set_lock_state,
        schema=lock_state_service_schema,
    )

    return True


class SurePetcareAPI:
    """Define a generic Sure Petcare object."""

    def __init__(
        self, hass: HomeAssistant, surepy: Surepy, ids: list[dict[str, Any]]
    ) -> None:
        """Initialize the Sure Petcare object."""
        self.hass = hass
        self.surepy = surepy
        self.ids = ids
        self._states = {}

    async def async_update(self, _: Any = None) -> None:
        """Get the latest data from the Pi-hole."""

        try:
            self._states = await self.surepy.get_entities()
        except SurePetcareError as error:
            _LOGGER.error("Unable to fetch data: %s", error)

        async_dispatcher_send(self.hass, TOPIC_UPDATE)

    async def set_lock_state(self, flap_id: int, state: str) -> None:
        """Update the lock state of a flap."""
        if state == LockState.UNLOCKED.name.lower():
            await self.surepy.unlock(flap_id)
        elif state == LockState.LOCKED_IN.name.lower():
            await self.surepy.lock_in(flap_id)
        elif state == LockState.LOCKED_OUT.name.lower():
            await self.surepy.lock_out(flap_id)
        elif state == LockState.LOCKED_ALL.name.lower():
            await self.surepy.lock(flap_id)
