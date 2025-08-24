"""Shark IQ Integration."""

import asyncio
import urllib.parse
from contextlib import suppress

import aiohttp

from sharkiq import (
    AylaApi,
    SharkIqAuthError,
    SharkIqAuthExpiringError,
    SharkIqNotAuthedError,
    get_ayla_api,
)

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    API_TIMEOUT,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
)
from .coordinator import SharkIqUpdateCoordinator


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


# ------------------------------
# Auth0 login helper
# ------------------------------
async def do_auth0_login(session: aiohttp.ClientSession, username: str, password: str) -> dict:
    """Perform Auth0 login like the SharkClean app and return tokens."""
    AUTH_DOMAIN = "https://login.sharkninja.com"
    CLIENT_ID = "wsguxrqm77mq4LtrTrwg8ZJUxmSrexGi"
    REDIRECT_URI = "com.sharkninja.shark://login.sharkninja.com/ios/com.sharkninja.shark/callback"
    SCOPE = "openid profile email offline_access"

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": AUTH_DOMAIN,
        "Referer": AUTH_DOMAIN + "/",
    }

    # 1. /authorize
    authorize_url = (
        f"{AUTH_DOMAIN}/authorize?"
        + urllib.parse.urlencode(
            {
                "os": "android",
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
            }
        )
    )
    async with session.get(authorize_url, headers=HEADERS, allow_redirects=True) as resp:
        parsed = urllib.parse.urlparse(str(resp.url))
        state = urllib.parse.parse_qs(parsed.query).get("state", [None])[0]
    if not state:
        raise CannotConnect("No state returned from /authorize")

    # 2. /u/login
    login_url = f"{AUTH_DOMAIN}/u/login?state={state}"
    form_data = {"state": state, "username": username, "password": password, "action": "default"}
    async with session.post(login_url, headers=HEADERS, data=form_data, allow_redirects=False) as resp:
        redirect_url = resp.headers.get("Location")

    code = None
    if redirect_url and redirect_url.startswith("/authorize/resume"):
        resume_url = AUTH_DOMAIN + redirect_url
        async with session.get(resume_url, headers=HEADERS, allow_redirects=False) as resp:
            final_url = resp.headers.get("Location")
            if final_url:
                parsed = urllib.parse.urlparse(final_url)
                code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
    else:
        parsed = urllib.parse.urlparse(redirect_url or "")
        code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]

    if not code:
        raise CannotConnect("No authorization code received from login flow")

    # 3. Exchange code for tokens
    token_url = f"{AUTH_DOMAIN}/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    async with session.post(token_url, headers={"Content-Type": "application/json"}, json=payload) as resp:
        token_data = await resp.json()

    if "access_token" not in token_data:
        raise SharkIqAuthError("Auth0 did not return an access token")

    return token_data


# ------------------------------
# Setup / teardown
# ------------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Initialize the SharkIQ platform via config entry."""
    if CONF_REGION not in config_entry.data:
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_REGION: SHARKIQ_REGION_DEFAULT},
        )

    session = async_create_clientsession(hass)

    # Run Auth0 login to verify credentials and fetch tokens
    try:
        tokens = await do_auth0_login(session, config_entry.data[CONF_USERNAME], config_entry.data[CONF_PASSWORD])
        LOGGER.debug("Got tokens during setup: %s", list(tokens.keys()))
    except Exception as exc:
        LOGGER.error("Auth0 login failed: %s", exc)
        raise exceptions.ConfigEntryNotReady from exc

    # Initialize Ayla API client (still required for device comms)
    ayla_api = get_ayla_api(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        websession=session,
        europe=(config_entry.data[CONF_REGION] == SHARKIQ_REGION_EUROPE),
    )

    try:
        async with asyncio.timeout(API_TIMEOUT):
            # We’ve already done Auth0 login, so just set cookie
            await ayla_api.async_set_cookie()
    except TimeoutError as exc:
        LOGGER.error("Timeout expired setting cookie")
        raise CannotConnect from exc

    # Discover devices
    shark_vacs = await ayla_api.async_get_devices(False)
    device_names = ", ".join(d.name for d in shark_vacs)
    LOGGER.debug("Found %d Shark IQ device(s): %s", len(shark_vacs), device_names)

    # Coordinator setup
    coordinator = SharkIqUpdateCoordinator(hass, config_entry, ayla_api, shark_vacs)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_disconnect_or_timeout(coordinator: SharkIqUpdateCoordinator):
    """Disconnect from vacuum."""
    LOGGER.debug("Disconnecting from Ayla API")
    async with asyncio.timeout(5):
        with suppress(SharkIqAuthError, SharkIqAuthExpiringError, SharkIqNotAuthedError):
            await coordinator.ayla_api.async_sign_out()


async def async_update_options(hass: HomeAssistant, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data[DOMAIN][config_entry.entry_id]
        with suppress(SharkIqAuthError):
            await async_disconnect_or_timeout(coordinator=domain_data)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
