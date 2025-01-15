"""Config flow for microBees integration."""

from collections.abc import Mapping
import logging
from typing import Any

from microBeesPy import MicroBees, MicroBeesException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import DOMAIN, MQTT_HOST_URL


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for microBees."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        scopes = ["read", "write"]
        return {"scope": " ".join(scopes)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or redirect to the MQTT configuration step."""

        microbees = MicroBees(
            session=aiohttp_client.async_get_clientsession(self.hass),
            token=data[CONF_TOKEN][CONF_ACCESS_TOKEN],
        )

        try:
            current_user = await microbees.getMyProfile()
        except MicroBeesException:
            return self.async_abort(reason="invalid_auth")
        except Exception:
            self.logger.exception("Unexpected error")
            return self.async_abort(reason="unknown")

        # Ensure unique ID is set
        await self.async_set_unique_id(str(current_user.id))

        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

            return await self.async_step_mqtt_custom(current_user)

        self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_mqtt_custom(
        self, user_input: dict[str, Any] | None = None, current_user=None
    ) -> ConfigFlowResult:
        """Handle the MQTT configuration step."""
        errors = {}

        if user_input is not None and current_user is not None:
            try:
                mqtt_username = f"beessmart:{user_input['mqtt_username']}"
                mqtt_data = {
                    "host": MQTT_HOST_URL,
                    "port": user_input.get("mqtt_port", 1883),
                    "username": mqtt_username,
                    "password": user_input.get("mqtt_password"),
                    "client_id": user_input.get("client_id"),
                }
                return self.async_create_entry(
                    title=current_user["username"],
                    data={
                        "current_user": current_user,
                        "mqtt": mqtt_data,
                    },
                )
            except Exception:
                self.logger.exception("MQTT configuration failed")
                errors["base"] = "mqtt_configuration_failed"

        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema(
                {
                    vol.Required("client_id"): str,
                    vol.Required("mqtt_username"): str,
                    vol.Required("mqtt_port", default=1883): int,
                    vol.Required("mqtt_password"): str,
                }
            ),
            errors=errors,
        )
