"""Main object for getting the PECO outage counter data."""
import httpx

from .const import API_URL, COUNTY_LIST


class PecoOutageApi:
    """API object for PECO outage counter."""

    def __init__(self, county: str) -> None:
        """Initialize the PECO outage counter API object."""
        if county not in COUNTY_LIST:
            raise InvalidCountyError(
                "County must be either BUCKS, CHESTER, DELAWARE, MONTGOMERY, PHILADELPHIA, YORK, or TOTAL, got {}".format(
                    county
                )
            )
        self.county = county

    async def get_outage_count(self):
        """Get the outage count for the given county."""
        async with httpx.AsyncClient() as client:
            r = await client.get(API_URL)  # pylint: disable=invalid-name

        if r.status_code != 200:
            raise HttpError("Error getting PECO outage counter data")

        if self.county == "TOTAL":
            return await self.get_outage_totals()

        data = r.json()
        try:
            areas = data["file_data"]["areas"]
        except KeyError as err:
            raise BadJSONError("Bad JSON returned from PECO outage counter") from err

        outage_dict = {}
        for area in areas:
            if area["name"] == self.county:
                customers_out = area["cust_a"]["val"]
                percent_customers_out = area["percent_cust_a"]["val"]
                outage_count = area["n_out"]
                customers_served = area["cust_s"]
                outage_dict = {
                    "customers_out": customers_out,
                    "percent_customers_out": percent_customers_out,
                    "outage_count": outage_count,
                    "customers_served": customers_served,
                }
        return outage_dict

    @staticmethod
    async def get_outage_totals():
        """Get the outage totals for the given county and mode."""
        async with httpx.AsyncClient() as client:
            r: httpx.Response = await client.get(  # pylint: disable=invalid-name
                API_URL
            )

        if r.status_code != 200:
            raise HttpError("Error getting PECO outage counter data")

        data: dict = r.json()
        try:
            totals: dict = data["file_data"]["totals"]
        except KeyError as err:
            raise BadJSONError("Bad JSON returned from PECO outage counter") from err

        return {
            "customers_out": totals["cust_a"]["val"],
            "percent_customers_out": totals["percent_cust_a"]["val"],
            "outage_count": totals["n_out"],
            "customers_served": totals["cust_s"],
        }


class InvalidCountyError(Exception):
    """Raised when the county is invalid."""


class HttpError(Exception):
    """Raised when the status code is not 200."""


class BadJSONError(Exception):
    """Raised when the JSON is invalid."""
