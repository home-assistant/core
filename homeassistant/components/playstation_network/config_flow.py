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
from psnawp_api.utils.misc import parse_npsso_token
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_ACCOUNT_ID, CONF_NPSSO, DOMAIN, NPSSO_LINK, PSN_LINK
from .coordinator import PlaystationNetworkConfigEntry
from .helpers import PlaystationNetwork

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_NPSSO): str})


class PlaystationNetworkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Playstation Network."""

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"friend": FriendSubentryFlowHandler}

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
                    user = await psn.get_user()
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
                    config_entries = self.hass.config_entries.async_entries(DOMAIN)
                    for entry in config_entries:
                        if user.account_id in {
                            subentry.unique_id for subentry in entry.subentries.values()
                        }:
                            return self.async_abort(
                                reason="already_configured_as_subentry"
                            )

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure flow for PlayStation Network integration."""
        return await self.async_step_reauth_confirm(user_input)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}

        entry = (
            self._get_reauth_entry()
            if self.source == SOURCE_REAUTH
            else self._get_reconfigure_entry()
        )

        if user_input is not None:
            try:
                npsso = parse_npsso_token(user_input[CONF_NPSSO])
                psn = PlaystationNetwork(self.hass, npsso)
                user = await psn.get_user()
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
            step_id="reauth_confirm" if self.source == SOURCE_REAUTH else "reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=errors,
            description_placeholders={
                "npsso_link": NPSSO_LINK,
                "psn_link": PSN_LINK,
            },
        )


class FriendSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding a friend."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Subentry user flow."""
        config_entry: PlaystationNetworkConfigEntry = self._get_entry()
        if config_entry.disabled_by:
            return self.async_abort(reason="config_entry_disabled")
        friends_list = config_entry.runtime_data.user_data.psn.friends_list

        if user_input is not None:
            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            if user_input[CONF_ACCOUNT_ID] in {
                entry.unique_id for entry in config_entries
            }:
                return self.async_abort(reason="already_configured_as_entry")
            for entry in config_entries:
                if user_input[CONF_ACCOUNT_ID] in {
                    subentry.unique_id for subentry in entry.subentries.values()
                }:
                    return self.async_abort(reason="already_configured")

            return self.async_create_entry(
                title=friends_list[user_input[CONF_ACCOUNT_ID]].online_id,
                data={},
                unique_id=user_input[CONF_ACCOUNT_ID],
            )

        if not friends_list:
            return self.async_abort(reason="no_friends")

        options = [
            SelectOptionDict(
                value=friend.account_id,
                label=friend.online_id,
            )
            for friend in friends_list.values()
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_ACCOUNT_ID): SelectSelector(
                            SelectSelectorConfig(options=options)
                        )
                    }
                ),
                user_input,
            ),
        )
