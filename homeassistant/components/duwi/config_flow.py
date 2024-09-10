"""Config flow for Duwi Smart Devices integration."""

import voluptuous as vol
from duwi_open_sdk.base_api import CustomerApi
from duwi_open_sdk.const import HTTP_ADDRESS, WEBSOCKET_ADDRESS, DuwiCode
from duwi_open_sdk.customer_client import CustomerClient
from homeassistant import config_entries

from .const import (
    ACCESS_TOKEN,
    ADDRESS,
    APP_KEY,
    APP_SECRET,
    APP_VERSION,
    CLIENT_MODEL,
    CLIENT_VERSION,
    DOMAIN,
    HOUSE_KEY,
    HOUSE_NAME,
    HOUSE_NO,
    PASSWORD,
    PHONE,
    REFRESH_TOKEN,
    WS_ADDRESS,
)


# Configuration class that handles flow initiated by the user for Duwi integration
class DuwiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Duwi."""

    async def async_step_user(self, user_input: dict = None) -> dict:
        """Handle a flow initiated by the user."""

        # Placeholder for error messages.
        errors = {}

        # Ensure DOMAIN data has been initialized in Home Assistant.
        self.hass.data.setdefault(DOMAIN, {})
        placeholders = {}

        # Check if user has provided app_key and app_secret.
        if user_input and all(
            user_input.get(key) for key in (APP_KEY, APP_SECRET, PHONE, PASSWORD)
        ):
            self.client = CustomerApi(
                address=HTTP_ADDRESS,
                ws_address=WEBSOCKET_ADDRESS,
                app_key=user_input[APP_KEY],
                app_secret=user_input[APP_SECRET],
                app_version=APP_VERSION,
                client_version=CLIENT_VERSION,
                client_model=CLIENT_MODEL,
            )
            lc = CustomerClient(self.client)

            # Authenticate the developer.
            auth_data = await lc.login(user_input[PHONE], user_input[PASSWORD])
            status = auth_data.get("code")

            # Handle status codes.
            if status == DuwiCode.SUCCESS.value:
                self.phone = user_input[PHONE]
                self.password = user_input[PASSWORD]
                self.access_token = auth_data.get("data", {}).get("accessToken")
                self.refresh_token = auth_data.get("data", {}).get("refreshToken")
                self.app_key = user_input[APP_KEY]
                self.app_secret = user_input[APP_SECRET]
                self.client.access_token = auth_data.get("data", {}).get("accessToken")
                hic = CustomerClient(self.client)

                # Fetch the house information.
                house_infos_data = await hic.fetch_house_info()
                house_infos_status = house_infos_data.get("code")

                if house_infos_status != DuwiCode.SUCCESS.value:
                    errors["base"] = "fetch_house_info_error"
                    placeholders["code"] = house_infos_status
                else:
                    if len(house_infos_data.get("data", {}).get("houseInfos", [])) == 0:
                        # Handle case where no houses are found.
                        errors["base"] = "no_houses_found_error"

                    self.houses = house_infos_data.get("data", {}).get("houseInfos", [])
                    return await self.async_step_select_house()

            if status != DuwiCode.SUCCESS.value:
                errors["base"] = "auth_error"
                placeholders["code"] = status
            elif status == DuwiCode.LOGIN_ERROR.value:
                errors["base"] = "invalid_auth"
                placeholders["code"] = status
            elif status == DuwiCode.SYS_ERROR.value:
                errors["base"] = "sys_error"
                placeholders["code"] = status

        # Show user input form (with error messages if any).
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(APP_KEY): str,
                    vol.Required(APP_SECRET): str,
                    vol.Required(PHONE): str,
                    vol.Required(PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_select_house(self, user_input: dict = None) -> dict:
        """Handle the selection of a house by the user."""

        # Placeholder for error messages.
        errors = {}
        # Placeholders for description placeholders.
        placeholders = {}

        # Retrieve the list of pre-existing self.houses to exclude.
        existing_house = self.hass.data[DOMAIN].get("existing_house", {})

        # Create a self.houses list excluding already existing ones.
        houses_list = {
            house["houseNo"]: house["houseName"]
            for house in self.houses
            if house["houseNo"] not in existing_house
        }

        houses_dict = {
            house["houseNo"]: {
                "house_name": house["houseName"],
                "house_key": house["lanSecretKey"],
            }
            for house in self.houses
            if house["houseNo"] not in existing_house
        }

        # If no self.houses remain, handle the error.
        if len(houses_list) == 0:
            errors["base"] = "no_houses_found_error"

        # With user's house selection, create an entry for the selected house.
        if user_input is not None:
            return self.async_create_entry(
                title=houses_dict[user_input["house_no"]].get("house_name"),
                data={
                    PHONE: self.phone,
                    PASSWORD: self.password,
                    ADDRESS: HTTP_ADDRESS,
                    ACCESS_TOKEN: self.access_token,
                    REFRESH_TOKEN: self.refresh_token,
                    WS_ADDRESS: WEBSOCKET_ADDRESS,
                    APP_KEY: self.app_key,
                    APP_SECRET: self.app_secret,
                    HOUSE_NO: user_input["house_no"],
                    HOUSE_NAME: houses_dict[user_input["house_no"]].get("house_name"),
                    HOUSE_KEY: houses_dict[user_input["house_no"]].get("house_key"),
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
            description_placeholders=placeholders,
        )
