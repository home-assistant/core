"""Config flow for Shark IQ integration."""

import urllib.parse
import voluptuous as vol
import aiohttp

from homeassistant import exceptions
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_REGION
from homeassistant.helpers import selector, aiohttp_client

from .const import (
    DOMAIN,
    LOGGER,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
    SHARKIQ_REGION_ELSEWHERE,
    SHARKIQ_REGION_OPTIONS,
)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid authentication."""


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
        raise CannotConnect("No authorization code received")

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
        raise InvalidAuth("Auth0 did not return an access token")

    return token_data


# ------------------------------
# Config Flow
# ------------------------------
SHARKIQ_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(
            CONF_REGION,
            default=SHARKIQ_REGION_DEFAULT,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=SHARKIQ_REGION_OPTIONS,
                translation_key="region",
            )
        ),
    }
)


async def _validate_input(hass, data) -> dict[str, str]:
    """Validate the user input allows us to connect."""
    session = aiohttp_client.async_create_clientsession(hass)
    try:
        tokens = await do_auth0_login(session, data[CONF_USERNAME], data[CONF_PASSWORD])
        LOGGER.debug("Got tokens in config flow: %s", list(tokens.keys()))
    except InvalidAuth as err:
        raise
    except Exception as err:
        raise CannotConnect from err

    return {"title": data[CONF_USERNAME]}


class SharkIqConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shark IQ."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _validate_input(self.hass, user_input)
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # fallback
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=SHARKIQ_SCHEMA,
            errors=errors,
        )
