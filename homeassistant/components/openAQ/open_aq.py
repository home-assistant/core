"""Platform for the openaq integration."""
# from homeassistant.components import OpenAQ
import logging

import openaq

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_air_quality_data(country_code, start_date, end_date):
    """Fetch air quality data from OpenAQ API.

    :param country_code: ISO country code.
    :param name: Location name.
    :param start_date: Start date in 'YYYY-MM-DD' format.
    :param end_date: End date in 'YYYY-MM-DD' format.
    :return: List of air quality data.
    """
    # Initialize the OpenAQ API
    api = openaq.OpenAQ()

    # Set your parameters for the measurements API call
    params = {
        "country": country_code,
        "date_from": start_date,
        "date_to": end_date,
        "limit": 1000,  # Adjust the limit as needed
        "df": True,  # Return results as a pandas DataFrame
        "index": "local",  # Set the index to 'local'
    }

    # Make the measurements API call
    status, resp = api.measurements(**params)
    if status == 200:
        # Successfully fetched data
        # Log the response instead of using print
        logger.info("fetch_air_quality_data response: %s", resp["results"])
        return resp["results"]

    # Handle the API error
    # Log the error instead of using print
    logger.error("Error fetching data. Status code: %s", status)
    return None


# if __name__ == "__main__":
# Set your parameters
# country_code = "SE"  # Country code for Sweden
# start_date = "2023-11-12"
# end_date = "2023-11-13"

# Call the function and print the response
# loop = asyncio.get_event_loop()
# air_quality_data = loop.run_until_complete(
# fetch_air_quality_data(country_code, start_date, end_date)
# )
