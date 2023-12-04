"""Class for fetching data from lightning API."""
from datetime import date

from .downloader import SmhiDownloader
from .smhi_geolocation_event import SmhiGeolocationEvent

APIURL_TEMPLATE = "https://opendata-download-lightning.smhi.se/api/version/latest/year/{}/month/{}/day/{}/data.json"
ICON_URL = "https://www.smhi.se/polopoly_fs/1.184284.1654612976!/image/blixt%20logo.png_gen/derivatives/Original_126px/image/blixt%20logo.png"


class SmhiLightning:
    """Class that uses the SMHI open lightning archive API to return the data."""

    async def get_lightning_impacts(self) -> list[SmhiGeolocationEvent]:
        """Return the most recent day of available lightning impacts."""
        months_with_31_days = [1, 3, 5, 7, 8, 10, 12]
        today = date.today()
        year = today.year
        month = today.month
        yesterday = today.day - 1
        if yesterday == 0:
            month = month - 1
            if month == 0:
                month = 12
                year = year - 1
            if month in months_with_31_days:
                yesterday = 31
            elif month == 2:
                yesterday = 28
            else:
                yesterday = 30

        smhi_downloader = SmhiDownloader()
        data = await smhi_downloader.download_json(APIURL_TEMPLATE.format(2023, 8, 25))
        if isinstance(data, dict):
            return self.parse_lightning_impacts(data)
        return []

    def parse_lightning_impacts(self, api_result: dict) -> list[SmhiGeolocationEvent]:
        """Convert results from API to a List of LightningImpacts."""

        lightning_impacts: list[SmhiGeolocationEvent] = []

        for impact in api_result["values"]:
            hour = int(impact["hours"])
            minute = int(impact["minutes"])
            second = int(impact["seconds"])
            latitude = float(impact["lat"])
            longitude = float(impact["lon"])
            peak_current = int(impact["peakCurrent"])

            name = (
                "Impact at: "
                + str(hour)
                + ":"
                + str(minute)
                + ":"
                + str(second)
                + "\nPeak Current: "
                + str(peak_current)
                + " kiloamperes"
            )

            lightning_impact = SmhiGeolocationEvent(
                name, latitude, longitude, ICON_URL, ICON_URL, "stationary"
            )

        lightning_impact = SmhiGeolocationEvent(
            name, latitude, longitude, ICON_URL, ICON_URL, "stationary", "lightning"
        )
        
        lightning_impacts.append(lightning_impact)

        return lightning_impacts
