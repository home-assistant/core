"""Config flow for ScorpionTrack."""

from __future__ import annotations

import logging
from typing import Any

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShareUnavailableError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SHARE_TOKEN, DEFAULT_NAME, DOMAIN
from .utils import mask_token

_LOGGER = logging.getLogger(__name__)


async def _async_validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate the provided share token or share URL."""
    client = ScorpionTrackClient(
        session=async_get_clientsession(hass),
        token=user_input[CONF_SHARE_TOKEN],
    )
    share = await client.async_get_share()

    if share.title:
        title = share.title
    elif share.vehicles:
        title = share.vehicles[0].display_name
    else:
        title = DEFAULT_NAME

    return {
        "token": share.token,
        "title": title,
        "unique_id": str(share.id),
    }


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
                info = await _async_validate_input(self.hass, user_input)
            except ScorpionTrackConnectionError as err:
                _LOGGER.warning(
                    "ScorpionTrack share validation could not connect for token %s: %s",
                    mask_token(user_input[CONF_SHARE_TOKEN]),
                    err,
                )
                errors["base"] = "cannot_connect"
            except ScorpionTrackInvalidTokenError as err:
                _LOGGER.warning(
                    "ScorpionTrack share validation rejected token %s: %s",
                    mask_token(user_input[CONF_SHARE_TOKEN]),
                    err,
                )
                errors["base"] = "invalid_token"
            except ScorpionTrackShareUnavailableError as err:
                _LOGGER.warning(
                    "ScorpionTrack share validation found unavailable share for token %s: %s",
                    mask_token(user_input[CONF_SHARE_TOKEN]),
                    err,
                )
                errors["base"] = "share_unavailable"
            except Exception:  # pragma: no cover - defensive logging
                _LOGGER.exception(
                    "Unexpected exception while validating ScorpionTrack share"
                )
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data={CONF_SHARE_TOKEN: info["token"]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_SHARE_TOKEN): str}),
            errors=errors,
        )
