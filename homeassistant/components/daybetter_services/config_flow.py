"""Config flow for DayBetter Services integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_TOKEN, CONF_USER_CODE, DOMAIN
from .daybetter_api import DayBetterApi


class DayBetterServicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DayBetter Services."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            user_code = user_input[CONF_USER_CODE]

            api = None
            api_with_token = None

            try:
                api = DayBetterApi()

                try:
                    integrate_result = await api.integrate(user_code)

                    if (
                        not integrate_result
                        or integrate_result.get("code") != 1
                        or "data" not in integrate_result
                        or "hassCodeToken" not in integrate_result["data"]
                    ):
                        errors["base"] = "invalid_code"
                    else:
                        token = integrate_result["data"]["hassCodeToken"]

                        api_with_token = DayBetterApi(token=token)

                        try:
                            await api_with_token.fetch_devices()
                            await api_with_token.fetch_pids()

                            return self.async_create_entry(
                                title="DayBetter Services",
                                data={
                                    CONF_USER_CODE: user_code,
                                    CONF_TOKEN: token,
                                },
                            )
                        except Exception:  # noqa: BLE001
                            errors["base"] = "cannot_connect"
                        finally:
                            if api_with_token is not None:
                                await api_with_token.close()
                finally:
                    if api is not None:
                        await api.close()

            except InvalidCode:
                errors["base"] = "invalid_code"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USER_CODE): str}),
            errors=errors,
            description_placeholders={
                "docs_url": "https://www.home-assistant.io/integrations/daybetter_services"
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidCode(HomeAssistantError):
    """Error to indicate invalid user code."""
