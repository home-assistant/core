"""Config flow for Baby Tracker (Nighp)."""

import logging
from typing import Any, override
from uuid import uuid4

import probatio
from pybabytracker import (
    AuthenticationError,
    BabyTrackerClient,
    BabyTrackerConnectionError,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_DEVICE_UUID, DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        probatio.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


async def _check_login(
    hass: HomeAssistant, email: str, password: str, device_uuid: str
) -> str | None:
    """Sign in once. Returns an error key for the form, or None when the login works."""
    # Not tied to an entry, so this check detaches its own session when it's done.
    session = async_create_clientsession(hass, auto_cleanup=False)
    client = BabyTrackerClient(
        email, password, device_uuid, DEVICE_NAME, session=session
    )
    try:
        await client.sign_in()
    except AuthenticationError:
        return "invalid_auth"
    except BabyTrackerConnectionError:
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error while checking the login")
        return "unknown"
    finally:
        await client.close()
        session.detach()
    return None


class BabyTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one Baby Tracker account."""

    VERSION = 1

    def __init__(self) -> None:
        """Set up the flow with a fresh device ID."""
        # Generated once per flow, and kept in the entry: this is Home Assistant's device ID.
        self._device_uuid = str(uuid4()).upper()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the account's email and password, then create the entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            error = await _check_login(
                self.hass, email, user_input[CONF_PASSWORD], self._device_uuid
            )
            if error is None:
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_DEVICE_UUID: self._device_uuid,
                    },
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA, user_input
            ),
            errors=errors,
        )
