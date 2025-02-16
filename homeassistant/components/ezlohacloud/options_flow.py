from datetime import datetime, timedelta
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .api import authenticate, signup


class EzloOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options flow for Ezlo HA Cloud integration."""

    async def async_step_init(self, user_input=None):
        """Check login status and show the correct UI."""
        config_data = self.config_entry.data
        is_logged_in = config_data.get("is_logged_in", False)
        username = config_data.get("user", {}).get("name", "Unknown User")
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
                    "logout": f"🔓 Logout ({username})",
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
        """Show configuration settings form properly."""
        if user_input is not None:
            # Save new configuration settings
            new_data = self.config_entry.data.copy()
            new_data.update(user_input)

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_abort(reason="config_saved")

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "sni_host", default=self.config_entry.data.get("sni_host", "")
                    ): str,
                    vol.Required(
                        "sni_port", default=self.config_entry.data.get("sni_port", 0)
                    ): int,
                    vol.Required(
                        "end_host", default=self.config_entry.data.get("end_host", "")
                    ): str,
                    vol.Required(
                        "end_port", default=self.config_entry.data.get("end_port", 0)
                    ): int,
                    vol.Required(
                        "fernet_token",
                        default=self.config_entry.data.get("fernet_token", ""),
                    ): str,
                }
            ),
        )

    async def async_step_force_logout(self, user_input=None):
        # """Forcefully log out when the token expires and return to the main options screen."""
        new_data = self.config_entry.data.copy()
        new_data["is_logged_in"] = False
        new_data["auth_token"] = None
        new_data["user"] = {}
        new_data["token_expiry"] = 0  # Clear expiry time

        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

        # Instead of showing logout message, return to the main options screen
        return await self.async_step_init()

    async def async_step_login(self, user_input=None):
        """Handles login authentication form."""
        errors = {}

        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]

            # Call authentication API
            auth_response = await self.hass.async_add_executor_job(
                authenticate, username, password
            )

            if auth_response.get("success"):
                expiry_time = auth_response["expires_at"]

                # Store login session persistently
                new_data = self.config_entry.data.copy()
                new_data["auth_token"] = auth_response["token"]
                new_data["user"] = auth_response["user"]
                new_data["is_logged_in"] = True
                new_data["token_expiry"] = expiry_time  # Store actual expiry

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                # Force refresh options menu after login
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
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
        """Handles manual logout action."""
        new_data = self.config_entry.data.copy()
        new_data["is_logged_in"] = False
        new_data["auth_token"] = None
        new_data["user"] = {}
        new_data["token_expiry"] = 0  # Clear expiry time

        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

        # Show logout success message only for manual logout
        return self.async_abort(reason="logged_out")

    async def async_step_signup(self, user_input=None):
        """Handles signup form."""
        errors = {}

        if user_input is not None:
            username = user_input["username"]
            email = user_input["email"]
            password = user_input["password"]

            # Call signup API
            signup_response = await self.hass.async_add_executor_job(
                signup, username, email, password
            )

            if signup_response.get("success"):
                return self.async_abort(reason="signup_successful")
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Register options flow steps."""
        return EzloOptionsFlowHandler(config_entry)
