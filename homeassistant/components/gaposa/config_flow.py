"""Config flow for Gaposa integration."""

from asyncio import timeout
from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp import ClientError
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


class GaposaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gaposa."""

    async def _async_validate_credentials(
        self, data: Mapping[str, Any]
    ) -> tuple[str | None, str]:
        """Attempt to authenticate against the Gaposa cloud.

        Returns a ``(user_uid, error)`` tuple. ``user_uid`` is the
        Firebase user identifier, stable per login regardless of
        client-membership order or count; ``None`` on any failure.
        ``error`` is ``""`` on success.
        """
        gaposa = Gaposa(
            data[CONF_API_KEY],
            websession=async_get_clientsession(self.hass),
        )
        try:
            async with timeout(10):
                await gaposa.login(data[CONF_USERNAME], data[CONF_PASSWORD])
            # Read clients before close() — pygaposa's close() may
            # invalidate state, and reading it after risks stale or
            # empty data on a future upstream refactor.
            if not gaposa.clients:
                return None, "no_clients"
            return gaposa.clients[0][1].uid, ""
        except (GaposaAuthException, FirebaseAuthException) as exc:
            _LOGGER.debug("Gaposa authentication failed: %s", exc)
            return None, "invalid_auth"
        except (ClientError, TimeoutError, OSError) as exc:
            _LOGGER.debug("Gaposa connection failed: %s", exc)
            return None, "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception during Gaposa login")
            return None, "unknown"
        finally:
            await gaposa.close()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_uid, error = await self._async_validate_credentials(user_input)
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(user_uid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_GATEWAY_NAME, data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
