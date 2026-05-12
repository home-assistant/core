"""Config flow for the FlowSpeech integration."""

from typing import Any

from flowspeech_sdk import (
    FlowSpeechAuthError,
    FlowSpeechClient,
    FlowSpeechConnectionError,
    FlowSpeechError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    API_KEYS_URL,
    CONF_API_KEY,
    CONF_VOICE,
    DEFAULT_VOICE,
    DOMAIN,
    SIGNUP_URL,
)


def _schema(
    api_key: str | None = None,
    voice: str | None = None,
) -> vol.Schema:
    """Return config-flow schema."""
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY, default=api_key or vol.UNDEFINED): str,
            vol.Optional(CONF_VOICE, default=voice or DEFAULT_VOICE): str,
        }
    )


async def _validate_input(hass, user_input: dict[str, Any]) -> None:
    """Validate FlowSpeech credentials."""
    client = FlowSpeechClient(api_key=user_input[CONF_API_KEY])
    try:
        await hass.async_add_executor_job(client.get_quota)
    except FlowSpeechAuthError as exc:
        raise InvalidAuth from exc
    except FlowSpeechConnectionError as exc:
        raise CannotConnect from exc
    except FlowSpeechError as exc:
        raise CannotConnect from exc


class FlowSpeechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FlowSpeech."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id("flowspeech")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="FlowSpeech",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_VOICE: user_input.get(CONF_VOICE) or DEFAULT_VOICE,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(
                user_input.get(CONF_API_KEY) if user_input else None,
                user_input.get(CONF_VOICE) if user_input else None,
            ),
            errors=errors,
            description_placeholders={
                "signup_url": SIGNUP_URL,
                "api_keys_url": API_KEYS_URL,
            },
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""
