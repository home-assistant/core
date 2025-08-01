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

MOCK_PEOPLE_ASSETS = [
    ImmichAsset.from_dict(
        {
            "id": "2242eda3-94c2-49ee-86d4-e9e071b6fbf4",
            "deviceAssetId": "1000092019",
            "ownerId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "deviceId": "5933dd9394fc6bf0493a26b4e38acca1076f30ab246442976d2917f1d57d99a1",
            "libraryId": None,
            "type": "IMAGE",
            "originalPath": "/usr/src/app/upload/upload/e7ef5713-9dab-4bd4-b899-715b0ca4379e/8e/a3/8ea31ee8-49c3-4be9-aa9d-b8ef26ba0abe.jpg",
            "originalFileName": "20250714_201122.jpg",
            "originalMimeType": "image/jpeg",
            "thumbhash": "XRgGDILGeMlPaJaMWIeagJcJSA==",
            "fileCreatedAt": "2025-07-14T18:11:22.648Z",
            "fileModifiedAt": "2025-07-14T18:11:25.000Z",
            "localDateTime": "2025-07-14T20:11:22.648Z",
            "updatedAt": "2025-07-26T10:16:39.131Z",
            "isFavorite": False,
            "isArchived": False,
            "isTrashed": False,
            "visibility": "timeline",
            "duration": "0:00:00.00000",
            "livePhotoVideoId": None,
            "people": [],
            "unassignedFaces": [],
            "checksum": "GcBJkDFoXx9d/wyl1xH89R4/NBQ=",
            "isOffline": False,
            "hasMetadata": True,
            "duplicateId": None,
            "resized": True,
        }
    ),
    ImmichAsset.from_dict(
        {
            "id": "046ac0d9-8acd-44d8-953f-ecb3c786358a",
            "deviceAssetId": "1000092018",
            "ownerId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "deviceId": "5933dd9394fc6bf0493a26b4e38acca1076f30ab246442976d2917f1d57d99a1",
            "libraryId": None,
            "type": "IMAGE",
            "originalPath": "/usr/src/app/upload/upload/e7ef5713-9dab-4bd4-b899-715b0ca4379e/f5/b4/f5b4b200-47dd-45e8-98a4-4128df3f9189.jpg",
            "originalFileName": "20250714_201121.jpg",
            "originalMimeType": "image/jpeg",
            "thumbhash": "XRgGDILHeMlPeJaMSJmKgJcIWQ==",
            "fileCreatedAt": "2025-07-14T18:11:21.582Z",
            "fileModifiedAt": "2025-07-14T18:11:24.000Z",
            "localDateTime": "2025-07-14T20:11:21.582Z",
            "updatedAt": "2025-07-26T10:16:39.131Z",
            "isFavorite": False,
            "isArchived": False,
            "isTrashed": False,
            "visibility": "timeline",
            "duration": "0:00:00.00000",
            "livePhotoVideoId": None,
            "people": [],
            "unassignedFaces": [],
            "checksum": "X6kMpPulu/HJQnKmTqCoQYl3Sjc=",
            "isOffline": False,
            "hasMetadata": True,
            "duplicateId": None,
            "resized": True,
        },
    ),
]

MOCK_TAGS_ASSETS = [
    ImmichAsset.from_dict(
        {
            "id": "ae3d82fc-beb5-4abc-ae83-11fcfa5e7629",
            "deviceAssetId": "2132393",
            "ownerId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "deviceId": "CLI",
            "libraryId": None,
            "type": "IMAGE",
            "originalPath": "/usr/src/app/upload/upload/e7ef5713-9dab-4bd4-b899-715b0ca4379e/07/d0/07d04d86-7188-4335-95ca-9bd9fd2b399d.JPG",
            "originalFileName": "20110306_025024.jpg",
            "originalMimeType": "image/jpeg",
            "thumbhash": "WCgSFYRXaYdQiYineIiHd4SghQUY",
            "fileCreatedAt": "2011-03-06T01:50:24.000Z",
            "fileModifiedAt": "2011-03-06T01:50:24.000Z",
            "localDateTime": "2011-03-06T02:50:24.000Z",
            "updatedAt": "2025-07-26T10:16:39.477Z",
            "isFavorite": False,
            "isArchived": False,
            "isTrashed": False,
            "visibility": "timeline",
            "duration": "0:00:00.00000",
            "livePhotoVideoId": None,
            "people": [],
            "checksum": "eNwN0AN2hEYZJJkonl7ylGzJzko=",
            "isOffline": False,
            "hasMetadata": True,
            "duplicateId": None,
            "resized": True,
        },
    ),
    ImmichAsset.from_dict(
        {
            "id": "b71d0d08-6727-44ae-8bba-83c190f95df4",
            "deviceAssetId": "2142137",
            "ownerId": "e7ef5713-9dab-4bd4-b899-715b0ca4379e",
            "deviceId": "CLI",
            "libraryId": None,
            "type": "IMAGE",
            "originalPath": "/usr/src/app/upload/upload/e7ef5713-9dab-4bd4-b899-715b0ca4379e/4a/f4/4af42484-86f8-47a0-958a-f32da89ee03a.JPG",
            "originalFileName": "20110306_024053.jpg",
            "originalMimeType": "image/jpeg",
            "thumbhash": "4AcKFYZPZnhSmGl5daaYeG859ytT",
            "fileCreatedAt": "2011-03-06T01:40:53.000Z",
            "fileModifiedAt": "2011-03-06T01:40:52.000Z",
            "localDateTime": "2011-03-06T02:40:53.000Z",
            "updatedAt": "2025-07-26T10:16:39.474Z",
            "isFavorite": False,
            "isArchived": False,
            "isTrashed": False,
            "visibility": "timeline",
            "duration": "0:00:00.00000",
            "livePhotoVideoId": None,
            "people": [],
            "checksum": "VtokCjIwKqnHBFzH3kHakIJiq5I=",
            "isOffline": False,
            "hasMetadata": True,
            "duplicateId": None,
            "resized": True,
        },
    ),
]
