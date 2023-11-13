"""Platform for the openaq integration."""
from __future__ import annotations

# from homeassistant.components import OpenAQ
import openaq


class MyOpenAirQuality:
    """Class for interacting with the OpenAQ API."""

    def __init__(self):
        """Initialize the OpenAQ API."""
        self.api = openaq.OpenAQ()

    def get_latest_data_in_sweden(self, **kwargs):
        """#  Calls the latest function with the country set to Sweden.

        # :param kwargs: Additional parameters to pass to the latest function.

        # :return: Response from the latest function.
        """
        # Set the country to Sweden
        kwargs["country"] = "SE"

        # Call the latest function using the OpenAQ API
        return self.api.latest(**kwargs)
