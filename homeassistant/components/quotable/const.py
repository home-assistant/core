"""Constants for the Quotable integration."""

from typing import Final

DOMAIN: Final = "quotable"
ENTITY_ID: Final = f"{DOMAIN}.quotable"

BASE_URL: Final = "https://api.quotable.io"
GET_TAGS_URL: Final = f"{BASE_URL}/tags"
SEARCH_AUTHORS_URL: Final = f"{BASE_URL}/search/authors"
FETCH_A_QUOTE_URL: Final = f"{BASE_URL}/quotes/random"

HTTP_CLIENT_TIMEOUT: Final = 10

SERVICE_FETCH_ALL_TAGS: Final = "fetch_all_tags"
SERVICE_SEARCH_AUTHORS: Final = "search_authors"
SERVICE_FETCH_A_QUOTE: Final = "fetch_a_quote"
SERVICE_UPDATE_CONFIGURATION: Final = "update_configuration"

ATTR_QUOTES: Final = "quotes"
ATTR_SELECTED_TAGS: Final = "selected_tags"
ATTR_SELECTED_AUTHORS: Final = "selected_authors"
ATTR_UPDATE_FREQUENCY: Final = "update_frequency"

DEFAULT_UPDATE_FREQUENCY: Final = 1800

EVENT_NEW_QUOTE_FETCHED: Final = f"{DOMAIN}_new_quote_fetched"
