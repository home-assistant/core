"""Config flow for Gaposa integration."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientConnectionError
from pygaposa import FirebaseAuthException, Gaposa, GaposaAuthException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_GATEWAY_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class GaposaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gaposa."""

    async def _async_validate_credentials(
        self, data: Mapping[str, Any]
    ) -> tuple[str | None, str]:
        """Attempt to authenticate against the Gaposa cloud.

        Returns a ``(client_id, error)`` tuple. ``client_id`` is ``None``
        on any failure and ``error`` is ``""`` on success.
        """
        gaposa = Gaposa(
            data[CONF_API_KEY],
            websession=async_get_clientsession(self.hass),
        )
        try:
            async with timeout(10):
                await gaposa.login(data[CONF_USERNAME], data[CONF_PASSWORD])
        except (GaposaAuthException, FirebaseAuthException) as exc:
            _LOGGER.debug("Gaposa authentication failed: %s", exc)
            return None, "invalid_auth"
        except ClientConnectionError as exc:
            _LOGGER.debug("Gaposa connection failed: %s", exc)
            return None, "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception during Gaposa login")
            return None, "unknown"
        finally:
            await gaposa.close()

        # The account-scoped Gaposa client id is stable across renames
        # and is the right thing to key the config entry on.
        if not gaposa.clients:
            return None, "unknown"
        return gaposa.clients[0][0].id, ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id, error = await self._async_validate_credentials(user_input)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(client_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_GATEWAY_NAME, data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, _entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when the stored credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a new password and validate it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            client_id, error = await self._async_validate_credentials(
                {
                    CONF_API_KEY: reauth_entry.data[CONF_API_KEY],
                    CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
            )
            if error:
                errors["base"] = error
            else:
                # Make sure the new credentials still point at the same account.
                await self.async_set_unique_id(client_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
