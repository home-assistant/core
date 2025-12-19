"""Hypon Cloud API integration."""

from dataclasses import dataclass
import logging
from time import sleep, time

import requests

from homeassistant.exceptions import ConfigEntryAuthFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class OverviewData:
    """Overview data class.

    This class represents the overview data for a Hypon Cloud plant.
    It contains information about the plant's capacity, power, energy production,
    device status, and environmental impact.
    """

    capacity: float
    capacity_company: str
    power: int
    company: str
    percent: int
    e_today: float
    e_total: float
    fault_dev_num: int
    normal_dev_num: int
    offline_dev_num: int
    wait_dev_num: int
    total_co2: int
    total_tree: float

    def __init__(self, **data) -> None:
        """Initialize the OverviewData class with data from the API.

        Args:
            data: Dictionary containing overview data from the API.
        """

        # The data attribute needs to be set manually because the API
        # may return more results than the existing data attributes.
        self.capacity = data.get("capacity", 0.0)
        self.capacity_company = data.get("capacity_company", "KW")
        self.power = data.get("power", 0)
        self.company = data.get("company", "W")
        self.percent = data.get("percent", 0)
        self.e_today = data.get("e_today", 0.0)
        self.e_total = data.get("e_total", 0.0)
        self.fault_dev_num = data.get("fault_dev_num", 0)
        self.normal_dev_num = data.get("normal_dev_num", 0)
        self.offline_dev_num = data.get("offline_dev_num", 0)
        self.wait_dev_num = data.get("wait_dev_num", 0)
        self.total_co2 = data.get("total_co2", 0)
        self.total_tree = data.get("total_tree", 0.0)


@dataclass
class PlantData:
    """Plant data class.

    This class represents the data for a Hypon Cloud plant.
    It contains information about the plant's location, energy production,
    identifiers, and status.
    """

    city: str
    country: str
    e_today: float
    e_total: float
    eid: int
    kwhimp: int
    micro: int
    plant_id: str
    plant_name: str
    plant_type: str
    power: int
    status: str

    def __init__(self, **data) -> None:
        """Initialize the PlantData class with data from the API.

        Args:
            data: Dictionary containing plant data from the API.
        """
        # The data attribute needs to be set manually because the API
        # may return more results than the existing data attributes.
        self.city = data.get("city", "")
        self.country = data.get("country", "")
        self.e_today = data.get("e_today", 0.0)
        self.e_total = data.get("e_total", 0.0)
        self.eid = data.get("eid", 0)
        self.kwhimp = data.get("kwhimp", 0)
        self.micro = data.get("micro", 0)
        self.plant_id = data.get("plant_id", "")
        self.plant_name = data.get("plant_name", "")
        self.plant_type = data.get("plant_type", "")
        self.power = data.get("power", 0)
        self.status = data.get("status", "")


class HyponCloud:
    """HyponCloud class."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the HyponCloud class.

        Args:
            username: The username for Hypon Cloud.
            password: The password for Hypon Cloud.
        """
        self.base_url = "https://api.hypon.cloud/v2"
        self.token_validity = 3600
        self.timeout = 10

        self.__username = username
        self.__password = password
        self.__token = ""
        self.__token_expires_at = 0

    def connect(self) -> bool:
        """Connect to Hypon Cloud and retrieve token."""

        if self.__token and self.__token_expires_at > time():
            return True

        url = self.base_url + "/login"
        data = {"username": self.__username, "password": self.__password}
        response = requests.post(url, json=data, timeout=self.timeout)
        if response.status_code != 200:
            # Temporary error, it could be the requests are being sent too fast from the same IP address.
            return False
        try:
            self.__token = response.json()["data"]["token"]
            self.__token_expires_at = int(time()) + self.token_validity
        except Exception as e:
            _LOGGER.error("Error connecting: %s", e)
            raise ConfigEntryAuthFailed("Can not log into Hypon Cloud.") from e
        return True

    def get_overview(self, retries: int = 3) -> OverviewData:
        """Get plant overview."""

        if not self.connect():
            return OverviewData()

        url = self.base_url + "/plant/overview"
        headers = {"authorization": "Bearer " + self.__token}
        response = requests.get(url, headers=headers, timeout=self.timeout)
        if response.status_code != 200:
            # Temporary error, it could be the requests are being sent too fast from the same IP address.
            if retries > 0:
                sleep(10)
                return self.get_overview(retries - 1)
            raise ConfigEntryAuthFailed("Can not get plant overview.")
        try:
            data = response.json()["data"]
        except KeyError as e:
            _LOGGER.error("Error getting plant list: %s", e)
            # Unknown error. Try again.
            if retries > 0:
                return self.get_overview(retries - 1)
        return OverviewData(**data)

    def get_list(self, retries: int = 3) -> list[dict]:
        """Get plant list."""
        url = self.base_url + "/plant/list2?page=1&page_size=10&refresh=true"
        headers = {"authorization": "Bearer " + self.__token}
        response = requests.get(url, headers=headers, timeout=self.timeout)
        if response.status_code != 200:
            # Temporary error, it could be the requests are being sent too fast from the same IP address.
            if retries > 0:
                sleep(10)
                return self.get_list(retries - 1)
            raise ConfigEntryAuthFailed("Can not get plant list.")
        try:
            data = response.json()["data"]
        except Exception as e:
            _LOGGER.error("Error getting plant list: %s", e)
            # Unknown error. Try again.
            if retries > 0:
                return self.get_list(retries - 1)
            raise
        return data
