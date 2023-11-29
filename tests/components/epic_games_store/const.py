"""Test constants."""
from homeassistant.components.epic_games_store.const import DOMAIN

from tests.common import load_json_object_fixture

MOCK_LANGUAGE = "fr"

DATA_ERROR_ATTRIBUTE_NOT_FOUND = load_json_object_fixture(
    "error_1004_attribute_not_found.json", DOMAIN
)

DATA_ERROR_WRONG_COUNTRY = load_json_object_fixture(
    "error_5222_wrong_country.json", DOMAIN
)

# free games
DATA_FREE_GAMES = load_json_object_fixture("free_games.json", DOMAIN)

DATA_ONE_FREE_GAME = load_json_object_fixture("free_game.json", DOMAIN)
