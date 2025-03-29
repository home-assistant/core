"""Config flow to configure Dreo."""

import hashlib
import logging
from typing import Any

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class DreoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Dreo config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Dreo flow."""

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password using MD5."""
        return hashlib.md5(password.encode("UTF-8")).hexdigest()

    async def _validate_login(
        self, username: str, password: str
    ) -> tuple[bool, str | None]:
        """Validate login credentials."""
        if not username or not password:
            return False, "invalid_auth"

        client = HsCloud(username, password)

        try:
            await self.hass.async_add_executor_job(client.login)
        except HsCloudException:
            return False, "cannot_connect"
        except HsCloudBusinessException:
            return False, "invalid_auth"
        return True, None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors = {}
        if user_input:
            username = user_input[CONF_USERNAME]
            hashed_password = self._hash_password(user_input[CONF_PASSWORD])

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            is_valid, error = await self._validate_login(username, hashed_password)
            if is_valid:
                return self.async_create_entry(
                    title=username,
                    data={CONF_USERNAME: username, CONF_PASSWORD: hashed_password},
                )
            errors["base"] = error if error else "unknown_error"
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
