"""Constants for the Collection Image integration tests."""

from pathlib import Path

TEST_IMAGE = Path(__file__).parent / "test.png"
DEFAULT_ENTITY_ID = "image.random_image"

MOCK_MEDIA_DIR_URI_1 = "media-source://mymedia"
MOCK_MEDIA_DIR_URI_EMPTY = "media-source://mymedia_empty"
MOCK_MEDIA_DIR_URI_BROWSE_ERROR = "media-source://mymedia_error"

MOCK_MEDIA_IMAGE_URI_1 = "media-source://mymedia/photo"
