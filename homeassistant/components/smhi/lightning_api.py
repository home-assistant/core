"""Class for fetching data from lightning API."""
from datetime import date
import json
from typing import Any, Optional
from urllib.request import urlopen

import aiohttp
from smhi.smhi_lib import SmhiForecastException

APIURL_TEMPLATE = "https://opendata-download-lightning.smhi.se/api/version/latest/year/{}/month/{}/day/{}/data.json"


class LightningImpact:
    """Class to hold lightning impact data."""

    def __init__(
        self,
        latitude: float,
        longitude: float,
        hour: int,
        minute: int,
        second: int,
        peakCurrent: int,
    ) -> None:
        """Set values."""
        self._latitude = latitude
        self._longitude = longitude
        self._hour = hour
        self._minute = minute
        self._second = second
        self._peakCurrent = peakCurrent

    @property
    def latitude(self) -> float:
        """Latitude coordinate of impact."""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Longitude coordinate of impact."""
        return self._longitude

    @property
    def hour(self) -> int:
        """Hour of impact."""
        return self._hour

    @property
    def minute(self) -> int:
        """Minute of impact."""
        return self._minute

    @property
    def second(self) -> int:
        """Second of impact."""
        return self._second

    @property
    def peakCurrent(self) -> int:
        """Peak current of the lightning in Kiloampere."""
        return self._peakCurrent


class LightningImpactAPI:
    """Implementation of the lightning impact API."""

    def __init__(self) -> None:
        """Initialise API with or without an API session."""
        self.session: Optional[aiohttp.ClientSession] = None

    def get_lightning_impact_api(self, year: str, month: str, day: str) -> Any:
        """Get data from the API."""
        api_url = APIURL_TEMPLATE.format(year, month, day)

        with urlopen(api_url) as response:
            data = response.read().decode("utf-8")
        json_data = json.loads(data)

        return json_data

    async def async_get_lightning_impact_api(
        self, year: int, month: int, day: int
    ) -> Any:
        """Get data from the API asynchroniously."""
        api_url = APIURL_TEMPLATE.format(year, month, day)

        is_new_session = False
        if self.session is None:
            self.session = aiohttp.ClientSession()
            is_new_session = True

        async with self.session.get(api_url) as response:
            if response.status != 200:
                if is_new_session:
                    await self.session.close()
                raise SmhiForecastException(
                    f"Failed to access lightning API with status code {response.status}"
                    + str(api_url)
                )
            data = await response.text()
            if is_new_session:
                await self.session.close()

            return json.loads(data)


class SmhiLightning:
    """Class that uses the SMHI open lightning archive API to return the data."""

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        session: Optional[aiohttp.ClientSession] = None,
        api: LightningImpactAPI = LightningImpactAPI(),
    ) -> None:
        """Set values."""
        self._year = year
        self._month = month
        self._day = day
        self._api = api

        if session:
            self._api.session = session

    def get_lightning_impact_most_recent(self) -> list[LightningImpact]:
        """Return the most recent day of available lightning impacts."""
        json_data = self._api.get_lightning_impact_api(
            str(date.year), str(date.month), str(date.day)
        )
        return _get_all_lightning_impacts_from_api(json_data)

    async def async_get_lightning_impact_most_recent(self) -> list[LightningImpact]:
        """Return the most recent day of available lightning impacts."""
        json_data = await self._api.async_get_lightning_impact_api(
            self._year, self._month, self._day
        )
        return _get_all_lightning_impacts_from_api(json_data)


def _get_all_lightning_impacts_from_api(api_result: dict) -> list[LightningImpact]:
    """Convert results from API to a List of LightningImpacts."""

    lightning_impacts: list[LightningImpact] = []

    for impact in api_result["values"]:
        hour = int(impact["hours"])
        minute = int(impact["minutes"])
        second = int(impact["seconds"])
        latitude = float(impact["lat"])
        longitude = float(impact["lon"])
        peakCurrent = int(impact["peakCurrent"])

        lightning_impact = LightningImpact(
            latitude, longitude, hour, minute, second, peakCurrent
        )

        lightning_impacts.append(lightning_impact)

    return lightning_impacts
