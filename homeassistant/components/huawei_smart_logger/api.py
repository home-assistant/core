"""Huawei Smart Logger 3000 API that pulls data from the Smart Logger website run within a home."""
import logging
import re

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .config_flow import CannotConnect, InvalidAuth
from .const import HTTP_TIMEOUT_SECONDS

_LOGGER = logging.getLogger(__name__)


class HuaweiSmartLogger3000API:
    """API Class for Huawei Smart Logger 3000."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Class initialization of our own API class."""
        self.hass = hass
        self.config_entry = config_entry
        self.USERNAME = config_entry.data[CONF_USERNAME]
        self.PASSWORD = config_entry.data[CONF_PASSWORD]
        self.HOST = config_entry.data[CONF_HOST]
        self.token = ""
        _LOGGER.debug("In api.py huaweismartlogger3000 class")
        super().__init__()

    def clean_string(self, input_string):
        """Remove non-alphanumeric characters and replace spaces with underscores."""
        cleaned_string = re.sub(r"[^a-zA-Z0-9 ]", "", input_string)
        cleaned_string = cleaned_string.replace(" ", "_")
        return cleaned_string.lower()

    async def fetch_data(self):
        """Log in to the smart logger get an authentication token then retrieve data."""
        authentication_data = {
            "langlist": "0",
            "usrname": self.USERNAME,
            "string": self.PASSWORD,
            "vercodeinput": "",
            "login": "Log+In",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://" + self.HOST + "/action/login",
                    data=authentication_data,
                    verify_ssl=False,
                    timeout=HTTP_TIMEOUT_SECONDS,
                ) as authentication_request:
                    if authentication_request.ok:
                        _LOGGER.debug("Authentication POST request successful")

                async with session.get(
                    "https://" + self.HOST + "/js/csrf.jst",
                    verify_ssl=False,
                    timeout=HTTP_TIMEOUT_SECONDS,
                ) as token_request:
                    if token_request.status != 200:
                        _LOGGER.error("Likely authentication failure")
                        raise InvalidAuth

                    pattern = r"tokenObj.value = \"(.*?)\";"
                    token_request_text = await token_request.text()
                    # Use re.search to find the match in the response body
                    token_match = re.search(pattern, token_request_text)

                    if token_match:
                        # Extract the matched string
                        extracted_string = token_match.group(1).strip()

                    _LOGGER.debug("Token we have retrieved is %s", extracted_string)

                    headersCSRF = {"X-CSRF-TOKEN": extracted_string}

                async with session.get(
                    "https://" + self.HOST + "/get_set_page_info.asp?type=88",
                    verify_ssl=False,
                    headers=headersCSRF,
                    timeout=HTTP_TIMEOUT_SECONDS,
                ) as data_request:
                    # print(third_request.text)
                    if token_request.status != 200:
                        _LOGGER.error("Likely authentication failure")
                        raise InvalidAuth

                    data_request_text = await data_request.text()
                    segments = [
                        segment.split("~") for segment in data_request_text.split("|")
                    ]

                    data_dict = {}

                    # Create a list of dictionaries from the segments
                    for segment in segments:
                        if len(segment) > 1:
                            if self.clean_string(segment[2]) in (
                                "soc",
                                "current_day_feedin_to_grid",
                                "gridtied_active_power",
                                "gridtied_reactive_power",
                                "load_power",
                                "active_power",
                                "reactive_power",
                                "todays_power_supply_from_grid",
                                "current_day_supply_from_grid",
                                "current_day_consumption",
                                "total_power_supply_from_grid",
                                "total_supply_from_grid",
                                "total_feedin_to_grid",
                                "total_power_consumption",
                                "pv_output_power",
                                "battery_chargedischarge_power",
                                "reactive_pv_power",
                                "reactive_ess_power",
                                "currentday_charge_capacity",
                                "currentday_discharge_capacity",
                                "total_charge",
                                "total_discharge",
                                "rated_ess_power",
                            ):
                                data_dict[self.clean_string(segment[2])] = segment[7]

        except InvalidAuth as e:
            _LOGGER.error("Invalid auth: %s", e)
        except TimeoutError as e:
            _LOGGER.error("Timeout Error: %s", e)
            raise CannotConnect
        except ConnectionRefusedError as e:
            _LOGGER.error("Connection Refused: %s", e)
            raise CannotConnect
        except aiohttp.ClientError as e:
            _LOGGER.error("Aiohttp Client Error: %s", e)
            raise CannotConnect
        return data_dict
