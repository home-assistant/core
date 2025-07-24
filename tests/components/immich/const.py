"""Constants for the Immich integration tests."""

from aioimmich.albums.models import ImmichAlbum

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

ALBUM_DATA = {
    "id": "721e1a4b-aa12-441e-8d3b-5ac7ab283bb6",
    "albumName": "My Album",
    "albumThumbnailAssetId": "0d03a7ad-ddc7-45a6-adee-68d322a6d2f5",
    "albumUsers": [],
    "assetCount": 1,
    "assets": [],
    "createdAt": "2025-05-11T10:13:22.799Z",
    "hasSharedLink": False,
    "isActivityEnabled": False,
    "ownerId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
    "owner": {
        "id": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
        "email": "admin@immich.local",
        "name": "admin",
        "profileImagePath": "",
        "avatarColor": "primary",
        "profileChangedAt": "2025-05-11T10:07:46.866Z",
    },
    "shared": False,
    "updatedAt": "2025-05-17T11:26:03.696Z",
}

MOCK_ALBUM_WITHOUT_ASSETS = ImmichAlbum.from_dict(ALBUM_DATA)

MOCK_ALBUM_WITH_ASSETS = ImmichAlbum.from_dict(
    {
        **ALBUM_DATA,
        "assets": [
            {
                "id": "2e94c203-50aa-4ad2-8e29-56dd74e0eff4",
                "deviceAssetId": "web-filename.jpg-1675185639000",
                "ownerId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
                "deviceId": "WEB",
                "libraryId": None,
                "type": "IMAGE",
                "originalPath": "upload/upload/e7ef5713-9dab-4bd4-b899-715b0ca4379e/b4/b8/b4b8ef00-8a6d-4056-91ff-7f86dc66e427.jpg",
                "originalFileName": "filename.jpg",
                "originalMimeType": "image/jpeg",
                "thumbhash": "1igGFALX8mVGdHc5aChJf5nxNg==",
                "fileCreatedAt": "2023-01-31T17:20:37.085+00:00",
                "fileModifiedAt": "2023-01-31T17:20:39+00:00",
                "localDateTime": "2023-01-31T18:20:37.085+00:00",
                "updatedAt": "2025-05-11T10:13:49.590401+00:00",
                "isFavorite": False,
                "isArchived": False,
                "isTrashed": False,
                "duration": "0:00:00.00000",
                "exifInfo": {},
                "livePhotoVideoId": None,
                "people": [],
                "checksum": "HJm7TVOP80S+eiYZnAhWyRaB/Yc=",
                "isOffline": False,
                "hasMetadata": True,
                "duplicateId": None,
                "resized": True,
            },
            {
                "id": "2e65a5f2-db83-44c4-81ab-f5ff20c9bd7b",
                "deviceAssetId": "web-filename.mp4-1675185639000",
                "ownerId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
                "deviceId": "WEB",
                "libraryId": None,
                "type": "IMAGE",
                "originalPath": "upload/upload/e7ef5713-9dab-4bd4-b899-715b0ca4379e/b4/b8/b4b8ef00-8a6d-4056-eeff-7f86dc66e427.mp4",
                "originalFileName": "filename.mp4",
                "originalMimeType": "video/mp4",
                "thumbhash": "1igGFALX8mVGdHc5aChJf5nxNg==",
                "fileCreatedAt": "2023-01-31T17:20:37.085+00:00",
                "fileModifiedAt": "2023-01-31T17:20:39+00:00",
                "localDateTime": "2023-01-31T18:20:37.085+00:00",
                "updatedAt": "2025-05-11T10:13:49.590401+00:00",
                "isFavorite": False,
                "isArchived": False,
                "isTrashed": False,
                "duration": "0:00:00.00000",
                "exifInfo": {},
                "livePhotoVideoId": None,
                "people": [],
                "checksum": "HJm7TVOP80S+eiYZnAhWyRaB/Yc=",
                "isOffline": False,
                "hasMetadata": True,
                "duplicateId": None,
                "resized": True,
            },
        ],
    }
)
