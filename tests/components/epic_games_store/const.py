"""Test constants."""
from homeassistant.components.epic_games_store.const import DOMAIN

from tests.common import load_json_object_fixture

MOCK_LOCALE = "fr"

DATA_ERROR_WRONG_COUNTRY = load_json_object_fixture("error_wrong_country.json", DOMAIN)

# free games
DATA_FREE_GAMES = load_json_object_fixture("free_games.json", DOMAIN)

DATA_ONE_FREE_GAME = load_json_object_fixture("free_game.json", DOMAIN)
