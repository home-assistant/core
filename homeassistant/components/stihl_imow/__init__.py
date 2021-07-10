"""The STIHL iMow integration."""
from __future__ import annotations

from datetime import timedelta
import typing

import async_timeout
from imow.api import IMowApi
from imow.common.exceptions import ApiMaintenanceError, LoginError
from imow.common.mowerstate import MowerState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_UPDATE_INTERVALL_SECONDS, API_UPDATE_TIMEOUT, DOMAIN, LOGGER
from .maps import ENTITY_STRIP_OUT_PROPERTIES
from .services import async_setup_services

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["sensor", "binary_sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up STIHL iMow from a config entry."""
    # TODO Store an API object for your platforms to access

    session = async_get_clientsession(hass)
    if "language" in entry.data:
        lang = entry.data["language"]
    else:
        lang = "en"

    config_email = (
        entry.data["user_input"]["email"]
        if "email" in entry.data["user_input"]
        else entry.data["user_input"]["username"]
    )
    imow_api = IMowApi(
        aiohttp_session=session,
        email=config_email,
        password=entry.data["user_input"]["password"],
        lang=lang,
    )
    try:
        await imow_api.get_token(force_reauth=True)

    except LoginError as err:

        # Raising ConfigEntryAuthFailed will cancel future updates
        # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        raise ConfigEntryAuthFailed from err
    except ApiMaintenanceError as err:
        raise UpdateFailed(f"Error communicating with API: {err}")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    intervall_seconds = (
        entry.data["polling_interval"]
        if "polling_interval" in entry.data
        else API_UPDATE_INTERVALL_SECONDS
    )
    mower_id = entry.data["mower"][0]["mower_id"]

    async def _async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(API_UPDATE_TIMEOUT):

                mower_state: MowerState = await imow_api.receive_mower_by_id(mower_id)
                mower_state.__dict__["statistics"] = await mower_state.get_statistics()
                #    del mower_state.__dict__["imow"]

                return mower_state

        except LoginError as err:

            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiMaintenanceError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ] = coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"imow_{entry.entry_id}",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=intervall_seconds),
    )

    # hass.data[DOMAIN][entry.entry_id] = {
    #     "mower": entry.data["mower"][0],
    #     "credentials": entry.data["user_input"],
    #     "api": imow_api,
    #     "language": lang,
    #     "polling_interval": intervall_seconds
    #     if intervall_seconds >= 120
    #     else API_UPDATE_INTERVALL_SECONDS,
    # }

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    await async_setup_services(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def extract_properties_by_type(
    mower_state: MowerState, property_python_type: typing.Any, negotiate=False
) -> tuple[dict, dict]:
    """Extract Properties used by different Sensors."""
    complex_entities: dict = {}
    entities = {}
    for mower_state_property in mower_state.__dict__:
        if type(mower_state.__dict__[mower_state_property]) in [dict]:
            complex_entities[mower_state_property] = mower_state.__dict__[
                mower_state_property
            ]
        else:
            if mower_state_property not in ENTITY_STRIP_OUT_PROPERTIES:
                if not negotiate:

                    if (
                        type(mower_state.__dict__[mower_state_property])
                        is property_python_type
                    ):
                        entities[mower_state_property] = mower_state.__dict__[
                            mower_state_property
                        ]
                else:
                    if (
                        type(mower_state.__dict__[mower_state_property])
                        is not property_python_type
                    ):
                        entities[mower_state_property] = mower_state.__dict__[
                            mower_state_property
                        ]

    for entity in complex_entities:
        for prop in complex_entities[entity]:
            property_identifier = f"{entity}_{prop}"
            if property_identifier not in ENTITY_STRIP_OUT_PROPERTIES:
                if not negotiate:
                    if type(complex_entities[entity][prop]) is property_python_type:
                        entities[property_identifier] = complex_entities[entity][prop]
                else:
                    if type(complex_entities[entity][prop]) is not property_python_type:
                        entities[property_identifier] = complex_entities[entity][prop]

    device = {
        "name": mower_state.name,
        "id": mower_state.id,
        "externalId": mower_state.externalId,
        "manufacturer": "STIHL",
        "model": mower_state.deviceTypeDescription,
        "sw_version": mower_state.softwarePacket,
    }
    return entities, device
