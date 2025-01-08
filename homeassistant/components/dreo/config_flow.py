"""Config flow to configure Dreo."""

import hashlib
import logging
from typing import Any

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class DreoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Dreo config flow."""

    VERSION = 1  # 添加版本号

    def __init__(self) -> None:
        """Initialize the Dreo flow."""
        self.manager: HsCloud | None = None

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
        if self.manager is None:
            self.manager = HsCloud(username, password)
        try:
            await self.hass.async_add_executor_job(self.manager.login)
        except HsCloudException:
            return False, "cannot_connect"
        except HsCloudBusinessException:
            return False, "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception during Dreo login")
            return False, "unknown"
        return True, None

    @callback
    def _show_form(self, errors=None):
        """Show form to the user."""
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors if errors else {}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if not user_input:
            return self._show_form()

        username = user_input[CONF_USERNAME]
        hashed_password = self._hash_password(user_input[CONF_PASSWORD])
        is_valid, error = await self._validate_login(username, hashed_password)
        if not is_valid:
            return self._show_form(errors={"base": error})

        return self.async_create_entry(
            title=username,
            data={CONF_USERNAME: username, CONF_PASSWORD: hashed_password},
        )
