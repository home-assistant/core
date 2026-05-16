"""Config flow for ScorpionTrack."""

import logging
from typing import Any

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SHARE_TOKEN, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _async_validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> ScorpionTrackShare:
    """Validate the provided share token or share URL."""
    try:
        normalized_token = ScorpionTrackClient.extract_token(
            user_input[CONF_SHARE_TOKEN]
        )
    except ValueError as err:
        raise ScorpionTrackInvalidTokenError(
            "Invalid ScorpionTrack share token"
        ) from err

    client = ScorpionTrackClient(
        session=async_get_clientsession(hass),
        token=normalized_token,
    )
    return await client.async_get_share()


def _share_title(share: ScorpionTrackShare) -> str:
    """Return the best config entry title for a share."""
    if share.title:
        return share.title
    if share.vehicles:
        return share.vehicles[0].display_name
    return DEFAULT_NAME


class ScorpionTrackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ScorpionTrack."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                share = await _async_validate_input(self.hass, user_input)
            except ScorpionTrackConnectionError:
                errors["base"] = "cannot_connect"
            except ScorpionTrackInvalidTokenError:
                errors["base"] = "invalid_token"
            except ScorpionTrackShareUnavailableError:
                errors["base"] = "share_unavailable"
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while validating ScorpionTrack share"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(share.id))
                self._abort_if_unique_id_configured()
                user_input[CONF_SHARE_TOKEN] = share.token
                return self.async_create_entry(
                    title=_share_title(share),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_SHARE_TOKEN): str}),
            errors=errors,
        )
