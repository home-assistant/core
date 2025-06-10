"""Ezlo HA Cloud integration options flow for Home Assistant."""

import base64
from datetime import datetime, timedelta
import json
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .api import authenticate, create_stripe_session, signup
from .frp_helpers import fetch_and_update_frp_config, start_frpc, stop_frpc

_LOGGER = logging.getLogger(__name__)


class EzloOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options flow for Ezlo HA Cloud integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self._config_entry = config_entry  # Add this line

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Register options flow steps."""
        return EzloOptionsFlowHandler(config_entry)

    async def async_step_init(self, user_input=None):
        """Check login status and show the correct UI."""
        config_data = self._config_entry.data
        is_logged_in = config_data.get("is_logged_in", False)
        token_expiry = config_data.get("token_expiry", 0)

        # Check if token is expired
        current_time = datetime.now().timestamp()
        if is_logged_in and current_time > token_expiry:
            # Token has expired, log out user and return to main menu
            return await self.async_step_force_logout()

        if is_logged_in:
            # User is logged in, show logout option
            return self.async_show_menu(
                step_id="init",
                menu_options={
                    "logout": "🔓 Logout",
                },
            )

        # User is NOT logged in, show login and configure options (main menu)
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "configure": "⚙️ Configure Port Settings",
                "login": "🔑 Login to Ezlo Cloud",
                "signup": "📝 Sign Up for Ezlo Cloud",
            },
        )

    async def async_step_configure(self, user_input=None):
        """Show configuration settings form."""
        if user_input is not None:
            # Save new configuration settings
            new_data = self._config_entry.data.copy()
            new_data.update(user_input)

            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return self.async_abort(reason="config_saved")

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "sni_host", default=self._config_entry.data.get("sni_host", "")
                    ): str,
                    vol.Required(
                        "sni_port", default=self._config_entry.data.get("sni_port", 0)
                    ): int,
                    vol.Required(
                        "end_host", default=self._config_entry.data.get("end_host", "")
                    ): str,
                    vol.Required(
                        "end_port", default=self._config_entry.data.get("end_port", 0)
                    ): int,
                    vol.Required(
                        "fernet_token",
                        default=self._config_entry.data.get("fernet_token", ""),
                    ): str,
                }
            ),
        )

    async def async_step_force_logout(self, user_input=None):
        # """Forcefully log out when the token expires and return to the main options screen."""
        new_data = self._config_entry.data.copy()
        new_data["is_logged_in"] = False
        new_data["auth_token"] = None
        new_data["user"] = {}
        new_data["token_expiry"] = 0  # Clear expiry time

        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

        # Instead of showing logout message, return to the main options screen
        return await self.async_step_init()

    async def async_step_login(self, user_input=None):
        """Handles login authentication form with HA instance UUID or empty ID if missing."""
        errors = {}

        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]

            system_uuid = await self.hass.helpers.instance_id.async_get()
            _LOGGER.info(
                f"Retrieved system UUID from instance_id.async_get: {system_uuid}"
            )

            if not system_uuid:
                system_uuid = ""
                _LOGGER.warning("Home Assistant UUID missing!")

            auth_response = await self.hass.async_add_executor_job(
                authenticate, username, password, system_uuid
            )

            if auth_response.get("success"):
                user_info = auth_response.get("user", {})
                _LOGGER.info("user info from login: %s", user_info)
                expiry_time = datetime.now() + timedelta(seconds=3600)

                new_data = self._config_entry.data.copy()
                new_data.update(
                    {
                        "auth_token": auth_response["token"],
                        "user": {
                            "uuid": user_info.get("uuid"),
                            "name": user_info.get("username", username),
                            "email": user_info.get("email", ""),
                            "ezlo_id": user_info.get("id", ""),
                        },
                        "is_logged_in": True,
                        "token_expiry": expiry_time.timestamp(),
                    }
                )
                # new_data["auth_token"] = auth_response["token"]
                # new_data["user"] = {"name": username, "email": ""}
                # new_data["is_logged_in"] = True
                # new_data["token_expiry"] = expiry_time.timestamp()

                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data
                )

                # UPDAT THE CONFIG TOML AND START THE FRPC CLIENT.
                try:
                    await fetch_and_update_frp_config(
                        hass=self.hass,
                        uuid=user_info.get("uuid"),
                        token=auth_response["token"],
                    )

                    await start_frpc(hass=self.hass, config_entry=self._config_entry)
                except Exception as err:
                    _LOGGER.error("Failed to fetch the server details: %s", err)
                    raise err

                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._config_entry.entry_id)
                )

                return self.async_abort(reason="login_successful")

            errors["base"] = auth_response.get("error", "Login failed")

        return self.async_show_form(
            step_id="login",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_logout(self, user_input=None):
        """Handle manual logout action."""
        new_data = self._config_entry.data.copy()
        new_data["is_logged_in"] = False
        new_data["auth_token"] = None
        new_data["user"] = {}
        new_data["token_expiry"] = 0  # Clear expiry time

        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        await stop_frpc(self.hass, self.hass.config_entries)
        # Show logout success message only for manual logout
        return self.async_abort(reason="logged_out")

    async def async_step_signup(self, user_input=None):
        """Handle signup form."""
        errors = {}

        if user_input is not None:
            username = user_input["username"]
            email = user_input["email"]
            password = user_input["password"]

            # Call signup API
            signup_response = await self.hass.async_add_executor_job(
                signup, username, email, password
            )

            _LOGGER.debug("Signup response: %s", signup_response)

            if signup_response.get("success") and "identity" in signup_response:
                try:
                    identity_token = signup_response["identity"]

                    padded = identity_token + "=" * (-len(identity_token) % 4)
                    decoded_bytes = base64.b64decode(padded)
                    decoded = json.loads(decoded_bytes)

                    user_uuid = decoded.get("PK_User")

                    stripe_response = await self.hass.async_add_executor_job(
                        create_stripe_session,
                        user_uuid,
                        "price_1RLKzGIOARqo54014CFxqSo3",
                    )

                    if stripe_response and stripe_response.get("checkout_url"):
                        return self.async_external_step(
                            step_id="stripe_redirect",
                            url=stripe_response["checkout_url"],
                        )

                    errors["base"] = "stripe_failed"

                except Exception as decode_error:
                    _LOGGER.error("Failed to decode Ezlo identity: %s", decode_error)
                    errors["base"] = "signup_failed"
            else:
                errors["base"] = signup_response.get("error", "Signup failed")

        return self.async_show_form(
            step_id="signup",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("email"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_stripe_redirect(self, user_input=None):
        return self.async_external_step_done(next_step_id="init")
