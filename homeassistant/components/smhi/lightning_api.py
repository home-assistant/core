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
        months_with_31_days = [
            1,
            3,
            5,
            7,
            8,
            10,
            12,
        ]  # Months that has 31 days in total

        # Today´s date
        today = date.today()
        year = today.year
        month = today.month

        # Most recent data available is yesterday, so take one day of from today
        yesterday = today.day - 1

        # Checks in case yesterday was another month or year than today
        if yesterday == 0:
            month = month - 1
            if month == 0:
                month = 12
                year = year - 1
            # Set yesterday value correctly according to what month it was
            if month in months_with_31_days:
                yesterday = 31
            elif month == 2:
                yesterday = 28
            else:
                yesterday = 30

        # Fetch the data using the SmhiDownloader class
        smhi_downloader = SmhiDownloader()
        # Date is currently set to static value to showcase functionality
        data = await smhi_downloader.download_json(APIURL_TEMPLATE.format(2023, 8, 25))
        if isinstance(data, dict):
            return self.parse_lightning_impacts(data)
        return []

    def parse_lightning_impacts(self, api_result: dict) -> list[SmhiGeolocationEvent]:
        """Convert results from API to a List of LightningImpacts."""

        # Empty array where the lightning entities will be stored
        lightning_impacts: list[SmhiGeolocationEvent] = []

        # Loop through all parameters returned by the API
        for impact in api_result["values"]:
            hour = int(
                impact["hours"]
            )  # Time of impact in hours in 24-hour digital clock
            minute = int(impact["minutes"])  # Time of impact in minutes
            second = int(impact["seconds"])  # Time of impact in seconds
            latitude = float(impact["lat"])  # Latitude coordinate of impact
            longitude = float(impact["lon"])  # Longitude coordinate of impact
            peak_current = int(
                impact["peakCurrent"]
            )  # Peak current of impact, including polarity

            # Name of entity
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

            # Create SmhiGeoLocationEvent of impact
            lightning_impact = SmhiGeolocationEvent(
                name, latitude, longitude, ICON_URL, ICON_URL, "stationary", "lightning"
            )

            # Add entity to list of entities
            lightning_impacts.append(lightning_impact)

        # Return list of entities
        return lightning_impacts
