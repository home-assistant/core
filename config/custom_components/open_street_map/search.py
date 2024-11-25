"""Module to search for addresses or coordinates using the OpenStreetMap API."""

import requests

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
        response = requests.get(NOMINATIM_URL, params=params, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.json()  # Return parsed JSON response
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as error:
        return {"error": f"Request failed: {error}"}
