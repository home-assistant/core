"""The microBees integration."""

from dataclasses import dataclass
from http import HTTPStatus

import aiohttp
from microBeesPy import MicroBees, MicrobeesMqtt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, PLATFORMS
from .coordinator import MicroBeesUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class HomeAssistantMicroBeesData:
    """Microbees data stored in the Home Assistant data object."""

    connector: MicroBees
    coordinator: MicroBeesUpdateCoordinator
    session: config_entry_oauth2_flow.OAuth2Session
    mqtt_client: MicrobeesMqtt


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up microBees from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    current_user = entry.data.get("current_user", {})
    mqtt_param = entry.data.get("mqtt", {})

    if isinstance(current_user, dict):
        gateSerial = current_user.get("gateSerial")
    elif hasattr(current_user, "gateSerial"):
        gateSerial = getattr(current_user, "gateSerial")

    gate = f"app{mqtt_param.get('client_id')}_{gateSerial}"

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as ex:
        if ex.status in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        ):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex

    microbees = MicroBees(token=session.token[CONF_ACCESS_TOKEN])

    mqtt_client = MicrobeesMqtt(
        broker=mqtt_param.get("host"),
        port=mqtt_param.get("port", 1883),
        username=mqtt_param.get("username"),
        password=mqtt_param.get("password"),
        client_id=gate,
    )

    coordinator = MicroBeesUpdateCoordinator(hass, microbees, mqtt_client)
    await coordinator.async_start()
    mqtt_client.subscribe(gate)

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = HomeAssistantMicroBeesData(
        connector=microbees,
        coordinator=coordinator,
        session=session,
        mqtt_client=mqtt_client,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
