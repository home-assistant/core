"""Ezlo HA Cloud integration options flow for Home Assistant."""

import asyncio
from datetime import datetime, timedelta
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .api import (
    authenticate,
    create_stripe_session,
    decode_jwt_payload,
    get_subscription_status,
    signup,
)
from .frp_helpers import fetch_and_update_frp_config, start_frpc, stop_frpc

_LOGGER = logging.getLogger(__name__)


class EzloOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options flow for Ezlo HA Cloud integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
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

        if is_logged_in and datetime.now().timestamp() > token_expiry:
            # Token has expired, log out user and return to main menu
            return await self.async_step_force_logout()

        if is_logged_in:
            # User is logged in, show logout option
            return self.async_show_menu(
                step_id="init",
                menu_options={
                    "view_status": "📋 View Payment Status",
                    "logout": "🔓 Logout",
                },
            )

        # User is NOT logged in, show login and configure options (main menu)
        return self.async_show_menu(
            step_id="init",
            menu_options={
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
        """Force logout the user and return to the main options step."""
        new_data = self._config_entry.data.copy()
        new_data.update(
            {
                "is_logged_in": False,
                "auth_token": None,
                "user": {},
                "token_expiry": 0,  # Clear expiry time
            }
        )
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        # Instead of showing logout message, return to the main options screen
        return await self.async_step_init()

    async def async_step_login(self, user_input=None):
        """Handle login authentication form with HA instance UUID or empty ID if missing."""
        errors = {}
        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]

            system_uuid = await self.hass.helpers.instance_id.async_get() or ""
            if not system_uuid:
                system_uuid = ""
                _LOGGER.warning("Home Assistant system_uuid missing!")
            auth_response = await authenticate(username, password, system_uuid)
            _LOGGER.info("Response: %s", auth_response)

            if auth_response["success"]:
                token = auth_response["data"]["token"]
                user_info = auth_response["data"]["user"]

                await self._handle_successful_login(
                    token,
                    {
                        "uuid": user_info["uuid"],
                        "username": user_info["username"],
                        "email": user_info["email"],
                        "ezlo_id": user_info["ezlo_id"],
                    },
                )
                return self.async_abort(reason="login_successful")
            errors["base"] = auth_response["error"]

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
        new_data.update(
            {
                "is_logged_in": False,
                "auth_token": None,
                "user": {},
                "token_expiry": 0,  # Clear expiry time
            }
        )
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        await stop_frpc(self.hass, self.hass.config_entries)
        return self.async_abort(reason="logged_out")

    async def async_step_signup(self, user_input=None):
        """Handle signup and provide Stripe payment link."""
        errors = {}

        if user_input is not None:
            username = user_input["username"]
            email = user_input["email"]
            password = user_input["password"]

            system_uuid = await self.hass.helpers.instance_id.async_get() or ""
            if not system_uuid:
                system_uuid = ""
                _LOGGER.warning("Home Assistant system_uuid missing!")

            signup_response = await signup(username, email, password, system_uuid)

            if signup_response.get("success") and "data" in signup_response:
                try:
                    token = signup_response["data"].get("token", "")
                    payload = decode_jwt_payload(token)
                    user_uuid = payload.get("uuid")

                    if not user_uuid:
                        raise ValueError("UUID missing in token payload")

                    # user_info = {
                    #     "uuid": user_uuid,
                    #     "username": username,
                    #     "email": email,
                    #     "ezlo_user_id": payload.get("ezlo_user_id", ""),
                    # }
                    # await self._handle_successful_login(token, user_info)

                    new_data = self._config_entry.data.copy()
                    new_data.update(
                        {
                            "auth_token": token,
                            "user": {
                                "uuid": user_uuid,
                                "username": username,
                                "email": email,
                                "ezlo_id": payload.get("ezlo_user_id", ""),
                            },
                        }
                    )
                    self.hass.config_entries.async_update_entry(
                        self._config_entry, data=new_data
                    )

                    base_url = (
                        self.hass.config.external_url
                        or self.hass.config.internal_url
                        or "http://localhost:8123"
                    )
                    back_url = f"{base_url}/config/integrations/integration/ezlohacloud"

                    stripe_response = await create_stripe_session(
                        user_uuid,
                        "price_1RLKzGIOARqo54014CFxqSo3",
                        back_url,
                    )

                    if stripe_response.get("success"):
                        data = stripe_response.get("data", {})
                        checkout_url = data.get("checkout_url")
                        # Start background polling
                        self.hass.async_create_task(
                            self._poll_payment_and_login(
                                user_uuid, token, username, email, payload
                            )
                        )
                        if checkout_url:
                            return self.async_show_form(
                                step_id="redirecting",
                                description_placeholders={"url": checkout_url},
                                data_schema=vol.Schema({}),
                            )
                        _LOGGER.warning(
                            "Stripe session success but no checkout_url found: %s",
                            stripe_response,
                        )
                        errors["base"] = "stripe_failed"

                except Exception as e:
                    _LOGGER.error("Signup token decode failed: %s", e)
                    errors["base"] = "signup_failed"
            else:
                errors["base"] = signup_response.get("error", "signup_failed")

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

    async def _handle_successful_login(self, token: str, user_info: dict) -> None:
        """Shared logic to handle successful login or signup."""
        expiry_time = datetime.now() + timedelta(seconds=3600)

        new_data = self._config_entry.data.copy()
        new_data.update(
            {
                "auth_token": token,
                "user": {
                    "uuid": user_info.get("uuid"),
                    "name": user_info.get("username"),
                    "email": user_info.get("email", ""),
                    "ezlo_id": user_info.get("ezlo_id", ""),
                },
                "is_logged_in": True,
                "token_expiry": expiry_time.timestamp(),
            }
        )

        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

        # UPDATE THE CONFIG TOML AND START THE FRPC CLIENT.
        try:
            await fetch_and_update_frp_config(
                hass=self.hass,
                uuid=user_info["uuid"],
                token=token,
            )
            await start_frpc(hass=self.hass, config_entry=self._config_entry)
        except Exception as err:
            _LOGGER.error("Failed to fetch the server details: %s", err)
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._config_entry.entry_id)
        )

    async def _poll_payment_and_login(
        self, user_uuid: str, token: str, username: str, email: str, payload: dict
    ):
        """Background task to poll payment status and login."""
        timeout = 15 * 60  # 15 minutes
        interval = 5  # seconds
        attempts = timeout // interval
        for _ in range(attempts):
            await asyncio.sleep(interval)
            status_response = await get_subscription_status(user_uuid)

            if status_response.get("success") and status_response.get("is_active"):
                _LOGGER.info("Subscription activated. Completing login")
                await self._handle_successful_login(
                    token,
                    {
                        "uuid": user_uuid,
                        "username": username,
                        "email": email,
                        "ezlo_id": payload.get("ezlo_user_id", ""),
                    },
                )
                return

        _LOGGER.warning("Polling timeout: User did not complete Stripe payment")

    async def async_step_view_status(self, user_input=None):
        """Display the subscription status form."""
        user_data = self._config_entry.data.get("user", {})
        user_uuid = user_data.get("uuid")

        status_text = "Unknown"
        url = self._config_entry.data.get("payment_url", "https://example.com/cloud")

        if user_uuid:
            status_response = await get_subscription_status(user_uuid)
            if status_response.get("success"):
                status = status_response.get("status", "unknown").capitalize()
                active = (
                    "✅ Active" if status_response.get("is_active") else "❌ Inactive"
                )
                status_text = f"{active} ({status})"
            else:
                status_text = f"Error: {status_response.get('error')}"

        return self.async_show_form(
            step_id="view_status",
            description_placeholders={
                "url": url,
                "status": status_text,
            },
            data_schema=vol.Schema({}),
        )

    async def async_step_stripe_finish(self, user_input=None):
        """Handle return from Stripe redirect with flow_id."""
        _LOGGER.info("Stripe checkout finished, resuming flow")

        # You can also update config here if needed:
        new_data = self._config_entry.data.copy()
        new_data["subscription_status"] = "paid"
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)

    async def async_step_redirecting(self, user_input=None):
        """User redirected from Stripe. Check payment status for completeness."""
        user_data = self._config_entry.data.get("user", {})
        user_uuid = user_data.get("uuid")

        _LOGGER.info("Stripe redirection for UUID: %s", user_uuid)

        # If background polling already logged in the user, just abort
        if self._config_entry.data.get("is_logged_in"):
            return self.async_abort(reason="login_successful")

        return self.async_abort(reason="stripe_redirect_finished")
