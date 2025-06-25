"""Config flow for the PlayStation Network integration."""

from collections.abc import Mapping
import logging
from typing import Any

from psnawp_api.core.psnawp_exceptions import (
    PSNAWPAuthenticationError,
    PSNAWPError,
    PSNAWPInvalidTokenError,
    PSNAWPNotFoundError,
)
from psnawp_api.models.user import User
from psnawp_api.utils.misc import parse_npsso_token
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import CONF_NPSSO, DOMAIN, NPSSO_LINK, PSN_LINK
from .helpers import PlaystationNetwork

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_NPSSO): str})


class PlaystationNetworkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Playstation Network."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        npsso: str | None = None
        if user_input is not None:
            try:
                npsso = parse_npsso_token(user_input[CONF_NPSSO])
            except PSNAWPInvalidTokenError:
                errors["base"] = "invalid_account"
            else:
                psn = PlaystationNetwork(self.hass, npsso)
                try:
                    user: User = await psn.get_user()
                except PSNAWPAuthenticationError:
                    errors["base"] = "invalid_auth"
                except PSNAWPNotFoundError:
                    errors["base"] = "invalid_account"
                except PSNAWPError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(user.account_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user.online_id,
                        data={CONF_NPSSO: npsso},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "npsso_link": NPSSO_LINK,
                "psn_link": PSN_LINK,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                npsso = parse_npsso_token(user_input[CONF_NPSSO])
                psn = PlaystationNetwork(self.hass, npsso)
                user: User = await psn.get_user()
            except PSNAWPAuthenticationError:
                errors["base"] = "invalid_auth"
            except (PSNAWPNotFoundError, PSNAWPInvalidTokenError):
                errors["base"] = "invalid_account"
            except PSNAWPError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user.account_id)
                self._abort_if_unique_id_mismatch(
                    description_placeholders={
                        "wrong_account": user.online_id,
                        CONF_NAME: entry.title,
                    }
                )

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_NPSSO: npsso},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={
                "npsso_link": NPSSO_LINK,
                "psn_link": PSN_LINK,
            },
        )
