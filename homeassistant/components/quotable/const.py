"""Constants for the Quotable integration."""

from typing import Final

DOMAIN: Final = "quotable"

BASE_URL: Final = "https://api.quotable.io"
GET_TAGS_URL: Final = f"{BASE_URL}/tags"
SEARCH_AUTHORS_URL: Final = f"{BASE_URL}/search/authors"
FETCH_A_QUOTE_URL: Final = f"{BASE_URL}/quotes/random"

HTTP_CLIENT_TIMEOUT: Final = 10

SERVICE_GET_TAGS: Final = "get_tags"
SERVICE_SEARCH_AUTHORS: Final = "search_authors"
SERVICE_FETCH_A_QUOTE: Final = "fetch_a_quote"

CONF_SELECTED_TAGS: Final = "selected_tags"
CONF_SELECTED_AUTHORS: Final = "selected_authors"
CONF_UPDATE_FREQUENCY: Final = "update_frequency"

DEFAULT_UPDATE_FREQUENCY: Final = 1800
