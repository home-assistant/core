"""Constants for the Immich integration tests."""

from aioimmich.albums.models import ImmichAlbum
from aioimmich.assets.models import ImmichAsset

from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_VERIFY_SSL,
)

MOCK_USER_DATA = {
    CONF_URL: "http://localhost",
    CONF_API_KEY: "abcdef0123456789",
    CONF_VERIFY_SSL: False,
}

MOCK_CONFIG_ENTRY_DATA = {
    CONF_HOST: "localhost",
    CONF_API_KEY: "abcdef0123456789",
    CONF_PORT: 80,
    CONF_SSL: False,
    CONF_VERIFY_SSL: False,
}

MOCK_ALBUM_WITHOUT_ASSETS = ImmichAlbum(
    "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
    "My Album",
    "This is my first great album",
    "0d03a7ad-ddc7-45a6-adee-68d322a6d2f5",
    1,
    [],
)

MOCK_ALBUM_WITH_ASSETS = ImmichAlbum(
    "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
    "My Album",
    "This is my first great album",
    "0d03a7ad-ddc7-45a6-adee-68d322a6d2f5",
    1,
    [
        ImmichAsset(
            "2e94c203-50aa-4ad2-8e29-56dd74e0eff4", "filename.jpg", "image/jpeg"
        ),
        ImmichAsset(
            "2e65a5f2-db83-44c4-81ab-f5ff20c9bd7b", "filename.mp4", "video/mp4"
        ),
    ],
)
