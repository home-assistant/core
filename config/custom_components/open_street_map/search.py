"""Module to search for addresses or coordinates using the OpenStreetMap API."""

import requests

from homeassistant.components.http import HomeAssistantView

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# Search for an address using OpenStreetMap's Nominatim API
def search_address(query: str):
    """Search for addresses.

    Args:
        query (str): The address to search for.

    Returns:
        dict: A dictionary containing the search results or an error message.

    """

    params = {"q": query, "format": "json"}
    try:
        response = requests.get(NOMINATIM_URL, params=params, timeout=5)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json()  # Return parsed JSON response
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as error:
        return {"error": f"Request failed: {error}"}


def get_Coordinates(json_data):
    """Extract coordinates from Json file."""

    try:
        # Get the first result's latitude and longitude
        latitude = float(json_data[0]["lat"])
        longitude = float(json_data[0]["lon"])
    except (IndexError, KeyError, ValueError):
        return {"error": "Coordinates could not be extracted"}
    else:
        return [latitude, longitude]


def get_address_coordinates(query: str):
    """Combine search_address and get_coordinates to return coordinates directly.

    Args:
        query (str): The address to search for.

    Returns:
        list: A list containing longitude and latitude as floats, or an error message.

    """
    json_response = search_address(query)

    if "error" in json_response:
        return {"error": json_response["error"]}

    return get_Coordinates(json_response)


class AddressSearchView(HomeAssistantView):
    """View to handle address search requests.

    Args:
        HomeAssistantView: Base class for Home Assistant views.

    Attributes:
        url (str): The URL endpoint for this view. Requests to this endpoint will invoke the view.
        name (str): The unique name of the view.
        requires_auth (bool): Indicates if authentication is required for this view.

    Returns:
    JSON: A JSON response containing search results or an error message.

    """

    url = "/search/search_address"
    name = "search:search_address"
    requires_auth = False  # Set to True if you want to require authentication

    async def get(self, request):
        """Handle GET requests to search for an address."""
        query = request.query.get("q")

        if not query:
            return self.json_message("Query parameter 'q' is required", status_code=400)

        # Perform the address search using the OpenStreetMap API
        results = await self.hass.async_add_executor_job(search_address, query)
        return self.json(results)
