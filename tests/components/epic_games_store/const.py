"""Test constants."""

from homeassistant.components.epic_games_store.const import DOMAIN

from tests.common import load_json_object_fixture

MOCK_LANGUAGE = "fr"
MOCK_COUNTRY = "FR"

DATA_ERROR_ATTRIBUTE_NOT_FOUND = load_json_object_fixture(
    "error_1004_attribute_not_found.json", DOMAIN
)

DATA_ERROR_WRONG_COUNTRY = load_json_object_fixture(
    "error_5222_wrong_country.json", DOMAIN
)

# free games
DATA_FREE_GAMES = load_json_object_fixture("free_games.json", DOMAIN)

DATA_FREE_GAMES_ONE = load_json_object_fixture("free_games_one.json", DOMAIN)

DATA_FREE_GAMES_CHRISTMAS_SPECIAL = load_json_object_fixture(
    "free_games_christmas_special.json", DOMAIN
)

DATA_FREE_GAMES_MYSTERY_SPECIAL = load_json_object_fixture(
    "free_games_mystery_special.json", DOMAIN
)
