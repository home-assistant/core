"""Constants for the Quotable integration."""

from typing import Final

DOMAIN: Final = "quotable"

BASE_URL: Final = "https://api.quotable.io"
GET_TAGS_URL: Final = f"{BASE_URL}/tags"
SEARCH_AUTHORS_URL: Final = f"{BASE_URL}/search/authors"
FETCH_A_QUOTE_URL: Final = f"{BASE_URL}/quotes/random"

SERVICE_GET_TAGS: Final = "get_tags"
SERVICE_SEARCH_AUTHORS: Final = "search_authors"
SERVICE_FETCH_A_QUOTE: Final = "fetch_a_quote"
