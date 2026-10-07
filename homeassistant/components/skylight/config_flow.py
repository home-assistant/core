"""Config flow for the Skylight integration.

Skylight uses OAuth2 authorization code + PKCE, but its OAuth server has a
single registered redirect URI (the Skylight website), so Home Assistant
cannot receive the callback. The flow therefore shows the authorize URL,
the user signs in in their browser, and pastes back the code (or the whole
callback URL) from the address bar.
"""

import logging
import secrets
from typing import Any, override

import probatio
from skylight_api import (
    SkylightAPI,
    SkylightAPIError,
    SkylightAuthError,
    authorize_url,
    exchange_authorization_code,
    extract_code,
    pkce_pair,
)

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_FINGERPRINT,
    CONF_FRAME_ID,
    CONF_FRAME_NAME,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_CODE = "code"

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_CODE): TextSelector(TextSelectorConfig())}
)


class SkylightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Skylight."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._verifier: str = ""
        self._challenge: str = ""
        self._device_fingerprint: str = ""
        self._token: dict[str, str] = {}
        self._frames: list[dict[str, str]] = []

    def _new_pkce_pair(self) -> None:
        """Generate a PKCE pair once per flow so it survives form errors."""
        if not self._verifier:
            self._verifier, self._challenge = pkce_pair()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the flow: show the authorize URL, exchange the pasted code."""
        errors: dict[str, str] = {}
        self._new_pkce_pair()

        if user_input is not None:
            code = extract_code(user_input[CONF_CODE])
            if not code:
                errors[CONF_CODE] = "invalid_code"
            else:
                # New fingerprint per install so multiple HA instances don't collide.
                self._device_fingerprint = secrets.token_hex(16)
                try:
                    self._token = await exchange_authorization_code(
                        async_get_clientsession(self.hass),
                        code=code,
                        code_verifier=self._verifier,
                        device_fingerprint=self._device_fingerprint,
                    )
                except SkylightAuthError as err:
                    _LOGGER.warning("OAuth code exchange failed: %s", err)
                    errors["base"] = "invalid_auth"
                except SkylightAPIError:
                    _LOGGER.exception("Skylight OAuth token endpoint error")
                    errors["base"] = "cannot_connect"
                else:
                    if self.source == SOURCE_REAUTH:
                        return await self._async_finish_reauth()
                    return await self._async_list_frames()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={"authorize_url": authorize_url(self._challenge)},
            errors=errors,
        )

    async def _async_list_frames(self) -> ConfigFlowResult:
        """List the frames on the account, straight to entry if there is one."""
        api = SkylightAPI(
            async_get_clientsession(self.hass),
            access_token=self._token[CONF_ACCESS_TOKEN],
            refresh_token=self._token[CONF_REFRESH_TOKEN],
            device_fingerprint=self._device_fingerprint,
        )
        try:
            self._frames = await api.get_frames()
        except SkylightAPIError:
            _LOGGER.exception("Failed to enumerate frames")
            return self.async_abort(reason="cannot_connect")
        if not self._frames:
            return self.async_abort(reason="no_frames")

        configured = {
            entry.data[CONF_FRAME_ID]
            for entry in self._async_current_entries(include_ignore=False)
        }
        available = [frame for frame in self._frames if frame["id"] not in configured]
        if not available:
            return self.async_abort(reason="all_frames_configured")
        if len(available) == 1:
            return await self._async_create_entry(available[0])

        return await self.async_step_pick_frame()

    async def async_step_pick_frame(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which frame to set up."""
        if user_input is not None:
            frame_id = user_input[CONF_FRAME_ID]
            frame = next(f for f in self._frames if f["id"] == frame_id)
            return await self._async_create_entry(frame)

        return self.async_show_form(
            step_id="pick_frame",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_FRAME_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=frame["id"], label=frame["name"])
                                for frame in self._frames
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def _async_create_entry(self, frame: dict[str, str]) -> ConfigFlowResult:
        """Create the config entry for a frame."""
        await self.async_set_unique_id(f"skylight_frame_{frame['id']}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=frame["name"],
            data={
                CONF_FRAME_ID: frame["id"],
                CONF_FRAME_NAME: frame["name"],
                CONF_TOKEN: {
                    CONF_ACCESS_TOKEN: self._token[CONF_ACCESS_TOKEN],
                    CONF_REFRESH_TOKEN: self._token[CONF_REFRESH_TOKEN],
                    CONF_DEVICE_FINGERPRINT: self._device_fingerprint,
                },
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Perform reauth when the refresh token is revoked."""
        return await self.async_step_user()

    async def _async_finish_reauth(self) -> ConfigFlowResult:
        """Update the tokens on the reauth entry and reload it."""
        reauth_entry = self._get_reauth_entry()
        return self.async_update_reload_and_abort(
            reauth_entry,
            data_updates={
                CONF_TOKEN: {
                    CONF_ACCESS_TOKEN: self._token[CONF_ACCESS_TOKEN],
                    CONF_REFRESH_TOKEN: self._token[CONF_REFRESH_TOKEN],
                    CONF_DEVICE_FINGERPRINT: self._device_fingerprint,
                },
            },
        )
