"""The surepetcare integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from surepy import Surepy, SurepyEntity
from surepy.enums import LockState
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
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
    vol.All(
        cv.deprecated(DOMAIN),
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
                        vol.Optional(CONF_PETS): vol.All(
                            cv.ensure_list, [cv.positive_int]
                        ),
                        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
                    },
                    cv.deprecated(CONF_FEEDERS),
                    cv.deprecated(CONF_FLAPS),
                    cv.deprecated(CONF_PETS),
                    cv.deprecated(CONF_SCAN_INTERVAL),
                )
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sure Petcare integration."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sure Petcare from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        surepy = Surepy(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            auth_token=entry.data[CONF_TOKEN],
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

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
