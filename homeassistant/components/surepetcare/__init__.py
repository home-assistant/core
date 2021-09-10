"""The surepetcare integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from surepy import Surepy, SurepyEntity
from surepy.enums import LockState
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_FLAP_ID,
    ATTR_LOCK_STATE,
    CONF_FEEDERS,
    CONF_FLAPS,
    CONF_PETS,
    DOMAIN,
    SERVICE_SET_LOCK_STATE,
    SURE_API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor", "sensor"]
SCAN_INTERVAL = timedelta(minutes=3)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_FEEDERS): vol.All(
                        cv.ensure_list, [cv.positive_int]
                    ),
                    vol.Optional(CONF_FLAPS): vol.All(
                        cv.ensure_list, [cv.positive_int]
                    ),
                    vol.Optional(CONF_PETS): vol.All(cv.ensure_list, [cv.positive_int]),
                    vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
                },
                cv.deprecated(CONF_FEEDERS),
                cv.deprecated(CONF_FLAPS),
                cv.deprecated(CONF_PETS),
                cv.deprecated(CONF_SCAN_INTERVAL),
            )
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sure Petcare integration."""
    conf = config[DOMAIN]
    hass.data.setdefault(DOMAIN, {})

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

    async def _update_method() -> dict[int, SurepyEntity]:
        """Get the latest data from Sure Petcare."""
        try:
            return await surepy.get_entities(refresh=True)
        except SurePetcareError as err:
            raise UpdateFailed(f"Unable to fetch data: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_update_method,
        update_interval=SCAN_INTERVAL,
    )

    hass.data[DOMAIN] = coordinator
    await coordinator.async_refresh()

    # load platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(platform, DOMAIN, {}, config)
        )

    lock_states = {
        LockState.UNLOCKED.name.lower(): surepy.sac.unlock,
        LockState.LOCKED_IN.name.lower(): surepy.sac.lock_in,
        LockState.LOCKED_OUT.name.lower(): surepy.sac.lock_out,
        LockState.LOCKED_ALL.name.lower(): surepy.sac.lock,
    }

    async def handle_set_lock_state(call):
        """Call when setting the lock state."""
        flap_id = call.data[ATTR_FLAP_ID]
        state = call.data[ATTR_LOCK_STATE]
        await lock_states[state](flap_id)
        await coordinator.async_request_refresh()

    lock_state_service_schema = vol.Schema(
        {
            vol.Required(ATTR_FLAP_ID): vol.All(
                cv.positive_int, vol.In(coordinator.data.keys())
            ),
            vol.Required(ATTR_LOCK_STATE): vol.All(
                cv.string,
                vol.Lower,
                vol.In(lock_states.keys()),
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
