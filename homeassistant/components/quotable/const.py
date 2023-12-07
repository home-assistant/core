"""Constants for the Quotable integration."""

from typing import Final

DOMAIN: Final = "quotable"
ENTITY_ID: Final = f"{DOMAIN}.quotable"

BASE_URL: Final = "https://api.quotable.io"
GET_TAGS_URL: Final = f"{BASE_URL}/tags"
GET_AUTHORS_URL: Final = f"{BASE_URL}/authors"
SEARCH_AUTHORS_URL: Final = f"{BASE_URL}/search/authors"
FETCH_A_QUOTE_URL: Final = f"{BASE_URL}/quotes/random"

HTTP_CLIENT_TIMEOUT: Final = 10

SERVICE_FETCH_ALL_TAGS: Final = "fetch_all_tags"
SERVICE_FETCH_ALL_AUTHORS: Final = "fetch_all_authors"
SERVICE_SEARCH_AUTHORS: Final = "search_authors"
SERVICE_FETCH_A_QUOTE: Final = "fetch_a_quote"
SERVICE_UPDATE_CONFIGURATION: Final = "update_configuration"

ATTR_QUOTES: Final = "quotes"
ATTR_SELECTED_TAGS: Final = "selected_tags"
ATTR_SELECTED_AUTHORS: Final = "selected_authors"
ATTR_UPDATE_FREQUENCY: Final = "update_frequency"
ATTR_STYLES: Final = "styles"
ATTR_BG_COLOR: Final = "bg_color"
ATTR_TEXT_COLOR: Final = "text_color"
ATTR_SUCCESS: Final = "success"
ATTR_DATA: Final = "data"
ATTR_ERROR: Final = "error"
ATTR_NAME: Final = "name"
ATTR_SLUG: Final = "slug"
ATTR_AUTHOR: Final = "author"
ATTR_CONTENT: Final = "content"

DEFAULT_BG_COLOR: Final = "#038fc7"
DEFAULT_TEXT_COLOR: Final = "#212121"
DEFAULT_UPDATE_FREQUENCY: Final = 1800

EVENT_NEW_QUOTE_FETCHED: Final = f"{DOMAIN}_new_quote_fetched"

ERROR_FETCHING_DATA_FROM_QUOTABLE_API: Final = "An error occurred while fetching data from the Quotable API. See logs for more details."
ERROR_MISSING_SEARCH_QUERY: Final = "A search query must be specified."
ERROR_UNKNOWN: Final = "An unknown error occurred. See logs for more details."
