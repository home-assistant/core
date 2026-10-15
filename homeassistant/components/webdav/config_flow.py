"""Config flow for the WebDAV integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiowebdav2.exceptions import (
    AccessDeniedError,
    MethodNotSupportedError,
    UnauthorizedError,
)
import probatio
import yarl

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_BACKUP_PATH, DOMAIN
from .helpers import async_create_client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
            )
        ),
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            )
        ),
        probatio.Optional(CONF_BACKUP_PATH, default="/"): str,
        probatio.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            )
        ),
    }
)


class WebDavConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WebDAV."""

    async def _async_validate_input(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Validate the connection to the WebDAV server and return errors."""
        client = async_create_client(
            hass=self.hass,
            url=data[CONF_URL],
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
            verify_ssl=data.get(CONF_VERIFY_SSL, True),
        )

        # .check() already does the most of the error handling and will return True
        # if we can access the root directory
        try:
            result = await client.check()
        except UnauthorizedError:
            return {"base": "invalid_auth"}
        except AccessDeniedError:
            return {"base": "access_denied"}
        except MethodNotSupportedError:
            return {"base": "invalid_method"}
        except Exception:
            _LOGGER.exception("Unexpected error")
            return {"base": "unknown"}

        if not result:
            return {"base": "cannot_connect"}
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_input(user_input)
            if not errors:
                self._async_abort_entries_match(
                    {
                        CONF_URL: user_input[CONF_URL],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                    }
                )

                parsed_url = yarl.URL(user_input[CONF_URL])
                return self.async_create_entry(
                    title=f"{user_input[CONF_USERNAME]}@{parsed_url.host}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_validate_input(
                {**reauth_entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "name": reauth_entry.title,
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                CONF_URL: reauth_entry.data[CONF_URL],
            },
        )
