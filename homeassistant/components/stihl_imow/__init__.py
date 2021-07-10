"""The STIHL iMow integration."""
from __future__ import annotations

import typing

from imow.api import IMowApi
from imow.common.mowerstate import MowerState

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_UPDATE_INTERVALL_SECONDS, DOMAIN
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
    await imow_api.get_token(force_reauth=True)
    hass.data.setdefault(DOMAIN, {})
    intervall_seconds = (
        entry.data["polling_interval"]
        if "polling_interval" in entry.data
        else API_UPDATE_INTERVALL_SECONDS
    )
    hass.data[DOMAIN][entry.entry_id] = {
        "mower": entry.data["mower"][0],
        "credentials": entry.data["user_input"],
        "api": imow_api,
        "language": lang,
        "polling_interval": intervall_seconds
        if intervall_seconds >= 120
        else API_UPDATE_INTERVALL_SECONDS,
    }
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
