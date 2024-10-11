"""Config flow for Duwi Smart Devices integration."""

from duwi_smarthome_sdk.base_api import CustomerApi
from duwi_smarthome_sdk.const import HTTP_ADDRESS, WEBSOCKET_ADDRESS, DuwiCode
from duwi_smarthome_sdk.customer_client import CustomerClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

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
class DuwiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Duwi."""

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self.client = None
        self.phone = None
        self.password = None
        self.access_token = None
        self.refresh_token = None
        self.app_key = None
        self.app_secret = None
        self.houses = None

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""

        # Placeholder for error messages.
        errors = {}

        # Ensure DOMAIN data has been initialized in Home Assistant.
        self.hass.data.setdefault(DOMAIN, {})
        placeholders: dict[str, str] = {}

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
                    self.houses = house_infos_data.get("data", {}).get("houseInfos", [])
                    return await self.async_step_select_house()
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

    async def async_step_select_house(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle the selection of a house by the user."""

        # Placeholder for error messages.
        errors = {}
        # Placeholders for description placeholders.
        placeholders: dict[str, str] = {}

        # Create a self.houses list excluding already existing ones.
        houses_list = {house["houseNo"]: house["houseName"] for house in self.houses}
        # If no self.houses remain, handle the error.
        if len(houses_list) == 0:
            errors["base"] = "no_houses_found_error"

        if user_input is not None:
            houses_dict: dict[str, dict[str, str]] = {
                house["houseNo"]: {
                    HOUSE_NAME: house["houseName"],
                    HOUSE_KEY: house["lanSecretKey"],
                }
                for house in self.houses
            }

            house_no = user_input.get(HOUSE_NO)
            if house_no is not None:
                house_info = houses_dict.get(house_no)
                if house_info is not None:
                    house_name = house_info.get(HOUSE_NAME)

                    # With user's house selection, create an entry for the selected house.
                    return self.async_create_entry(
                        title=house_name if house_name else "Default House Name",
                        data={
                            PHONE: self.phone,
                            PASSWORD: self.password,
                            ADDRESS: HTTP_ADDRESS,
                            ACCESS_TOKEN: self.access_token,
                            REFRESH_TOKEN: self.refresh_token,
                            WS_ADDRESS: WEBSOCKET_ADDRESS,
                            APP_KEY: self.app_key,
                            APP_SECRET: self.app_secret,
                            HOUSE_NO: user_input[HOUSE_NO],
                            HOUSE_NAME: houses_dict[user_input[HOUSE_NO]].get(
                                HOUSE_NAME
                            ),
                            HOUSE_KEY: houses_dict[user_input[HOUSE_NO]].get(HOUSE_KEY),
                        },
                    )

        # If no house has been selected yet, show the selection form.
        return self.async_show_form(
            step_id="select_house",
            data_schema=vol.Schema(
                {
                    vol.Required(HOUSE_NO): vol.In(houses_list),
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
