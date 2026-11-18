"""Config flow for the Ablago integration."""

from collections.abc import Mapping
from typing import Any, override
from urllib.parse import urlsplit

from ablago import AblagoAuthError, AblagoConnectionError, AblagoError, AblagoSSLError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL

from .const import DOMAIN, LOGGER
from .coordinator import create_client

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): str,
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
        probatio.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)
STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
)
# Home Assistant keeps URLs out of translated strings; the example comes in as a placeholder.
PLACEHOLDERS = {"example_url": "https://ablago.example.org"}


def _title(url: str) -> str:
    """Name a new entry after the host; users rename the device per person, e.g. to "Ablago · Lena"."""
    return urlsplit(url.strip()).netloc or url


class AblagoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ablago.

    One entry per person: every person creates their own key of the level "counters only" in Ablago.
    """

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for address and key, then try them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {
                **user_input,
                CONF_URL: user_input[CONF_URL].strip().rstrip("/"),
            }
            self._async_abort_entries_match(
                {CONF_URL: user_input[CONF_URL], CONF_API_KEY: user_input[CONF_API_KEY]}
            )
            errors = await self._validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title=_title(user_input[CONF_URL]), data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            description_placeholders=PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change address, key or certificate check of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input = {
                **user_input,
                CONF_URL: user_input[CONF_URL].strip().rstrip("/"),
            }
            self._async_abort_entries_match(
                {CONF_URL: user_input[CONF_URL], CONF_API_KEY: user_input[CONF_API_KEY]}
            )
            errors = await self._validate_input(user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=user_input)

        suggested = user_input or {
            CONF_URL: entry.data[CONF_URL],
            CONF_VERIFY_SSL: entry.data.get(CONF_VERIFY_SSL, True),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested
            ),
            description_placeholders=PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth when Ablago rejects the key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            self._async_abort_entries_match(
                {CONF_URL: data[CONF_URL], CONF_API_KEY: data[CONF_API_KEY]}
            )
            # The form only has the key, so address problems are shown for the form.
            if found := await self._validate_input(data):
                errors = {"base": next(iter(found.values()))}
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"url": entry.data[CONF_URL]},
            errors=errors,
        )

    async def _validate_input(self, data: dict[str, Any]) -> dict[str, str]:
        """Try address and key by fetching the counters once."""
        try:
            client = create_client(self.hass, data)
        except ValueError:
            return {CONF_URL: "invalid_url"}
        try:
            await client.zaehler()
        except AblagoAuthError:
            return {"base": "invalid_auth"}
        except AblagoSSLError:
            return {CONF_URL: "ssl_error"}
        except AblagoConnectionError:
            return {CONF_URL: "cannot_connect"}
        except AblagoError as err:
            if err.status is not None and 300 <= err.status < 400:
                return {CONF_URL: "redirect"}
            return {CONF_URL: "not_ablago"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception while trying Ablago")
            return {"base": "unknown"}
        return {}
