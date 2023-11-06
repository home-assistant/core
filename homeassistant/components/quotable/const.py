"""Constants for the Quotable integration."""

from typing import Final

DOMAIN: Final = "quotable"

BASE_URL: Final = "https://api.quotable.io"
GET_TAGS_URL: Final = f"{BASE_URL}/tags"
SEARCH_AUTHORS_URL: Final = f"{BASE_URL}/search/authors"
GET_QUOTES_URL: Final = f"{BASE_URL}/quotes/random"
