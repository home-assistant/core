"""Config flow for Duwi Smart Hub integration."""

import logging

import voluptuous as vol
from duwi_smarthome_sdk.api.account import AccountClient
from duwi_smarthome_sdk.api.house import HouseInfoClient
from duwi_smarthome_sdk.const.status import Code

from homeassistant import config_entries

from .const import DOMAIN, APP_VERSION, CLIENT_MODEL, CLIENT_VERSION

_LOGGER = logging.getLogger(__name__)


# Configuration class that handles flow initiated by the user for Duwi integration
class DuwiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    # Use version 1 for the configuration flow
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """
        Handle a flow initiated by the user.

        This function tries to authenticate using the user-provided credentials (if any),
        processes the server response, and navigates to the next configuration flow step accordingly.
        """

        # Placeholder for error messages
        errors = {}

        # Ensure DOMAIN data has been initialized in Home Assistant
        self.hass.data.setdefault(DOMAIN, {})

        # Check if user has provided app_key and app_secret
        if user_input and user_input.get("app_key") and user_input.get("app_secret"):

            # Initialize account client with provided details
            lc = AccountClient(
                app_key=user_input["app_key"],
                app_secret=user_input["app_secret"],
                app_version=APP_VERSION,
                client_version=CLIENT_VERSION,
                client_model=CLIENT_MODEL,
            )

            # Try to authenticate with given credentials
            status = await lc.auth(user_input["app_key"], user_input["app_secret"])
            # Process returned status codes and handle potential errors
            if status == Code.APP_KEY_ERROR.value:
                errors["base"] = "auth_error"
            elif status == Code.SIGN_ERROR.value:
                errors["base"] = "sign_error"
            elif status == Code.SYS_ERROR.value:
                errors["base"] = "sys_error"
            elif status == Code.SUCCESS.value:
                # On success, Store credentials in Home Assistant and go to next configuration step
                self.hass.data[DOMAIN]["app_key"] = user_input["app_key"]
                self.hass.data[DOMAIN]["app_secret"] = user_input["app_secret"]
                return await self.async_step_auth()
            else:
                # Handle any other unexpected error status
                errors["base"] = "unknown_error"

        # Show user input form (with error messages if any)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("app_key"): str,
                    vol.Required("app_secret"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_auth(self, user_input=None):
        """
        Handle the authentication step in the configuration flow.

        This step authenticates the user with their phone number and password, fetches
        house information upon successful login, and transitions to house selection.
        """
        errors = {}
        if user_input and user_input.get("phone") and user_input.get("password"):

            # Access the stored app credentials from previous step
            app_key = self.hass.data[DOMAIN]["app_key"]
            app_secret = self.hass.data[DOMAIN]["app_secret"]
            phone = user_input["phone"]
            password = user_input["password"]

            # Initialize the AccountClient for authentication
            lc = AccountClient(
                app_key=app_key,
                app_secret=app_secret,
                app_version=APP_VERSION,
                client_version=CLIENT_VERSION,
                client_model=CLIENT_MODEL,
            )

            # Perform the login with provided phone number and password
            status, auth_token = await lc.login(phone, password)

            # Process the login response and handle accordingly
            if status == Code.SUCCESS.value:
                # Initiate HouseInfoClient for house info retrieval
                hic = HouseInfoClient(
                    app_key=app_key,
                    app_secret=app_secret,
                    access_token=auth_token.access_token,
                    app_version=APP_VERSION,
                    client_version=CLIENT_VERSION,
                    client_model=CLIENT_MODEL,
                )
                # Fetch the house information
                status, house_infos = await hic.fetch_house_info()

                if house_infos:
                    # Store house information and tokens in Home Assistant for use in further steps
                    self.hass.data[DOMAIN]["houses"] = house_infos
                    self.hass.data[DOMAIN]["access_token"] = auth_token.access_token
                    self.hass.data[DOMAIN]["refresh_token"] = auth_token.refresh_token
                    # Move to the next configuration step to select a house
                    return await self.async_step_select_house()
                else:
                    # Handle case where no houses are found
                    errors["base"] = "no_houses_found_error"
            elif status == Code.LOGIN_ERROR.value:
                # Handle login error status
                errors["base"] = "invalid_auth"
            elif status == Code.SYS_ERROR.value:
                # Handle system error status
                errors["base"] = "sys_error"
            else:
                # Handle unknown error status
                errors["base"] = "unknown_error"

        # Show the authentication form with constructed errors
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required("phone"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_house(self, user_input=None):
        """
        Handle the selection of a house by the user.

        In this step, the function determines the list of houses the user can select from,
        processes their selection, stores the selected house's details, and creates an entry for it.
        """

        # Placeholder for error messages.
        errors = {}

        # Extract houses data from Home Assistant.
        houses = self.hass.data[DOMAIN]["houses"]
        # Retrieve the list of pre-existing houses to exclude.
        existing_house = self.hass.data[DOMAIN].get("existing_house", [])

        # Create a houses list excluding already existing ones.
        houses_list = {
            house.house_no: house.house_name
            for house in houses
            if house.house_no not in existing_house
        }

        # If no houses remain, handle the error.
        if len(houses_list) == 0:
            errors["base"] = "no_houses_found_error"

        # With user's house selection, create an entry for the selected house.
        if user_input is not None:
            return self.async_create_entry(
                title=houses_list[user_input["house_no"]],
                data={
                    "access_token": self.hass.data[DOMAIN]["access_token"],
                    "refresh_token": self.hass.data[DOMAIN]["refresh_token"],
                    "house_no": user_input["house_no"],
                    "house_name": houses_list[user_input["house_no"]],
                    "app_key": self.hass.data[DOMAIN]["app_key"],
                    "app_secret": self.hass.data[DOMAIN]["app_secret"],
                },
            )

        # If no house has been selected yet, show the selection form.
        return self.async_show_form(
            step_id="select_house",
            data_schema=vol.Schema(
                {
                    vol.Required("house_no"): vol.In(houses_list),
                }
            ),
            errors=errors,
        )
