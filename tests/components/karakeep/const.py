"""Constants for Karakeep tests."""

from aiokarakeep import KarakeepStats

TEST_STATS = KarakeepStats(
    num_bookmarks=10,
    num_favorites=2,
    num_archived=3,
    num_highlights=4,
    num_lists=5,
    num_tags=6,
)

TEST_VERSION = "0.32.0"
TEST_TOKEN = "test-token"
TEST_URL = "https://karakeep.example.com"
