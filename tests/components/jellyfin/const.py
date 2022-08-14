"""Constants for the Jellyfin integration tests."""

from typing import Final

from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE

TEST_URL: Final = "https://example.com"
TEST_USERNAME: Final = "test-username"
TEST_PASSWORD: Final = "test-password"

MOCK_USER_ID = "123"
MOCK_DEVICE_ID = "Home Assistant"
MOCK_AUTH_TOKEN = "a4c12c43edef56925ba65328a0e96325"

MOCK_SUCCESFUL_CONNECTION_STATE: Final = {"State": CONNECTION_STATE["ServerSignIn"]}
MOCK_SUCCESFUL_LOGIN_RESPONSE: Final = {"AccessToken": "Test"}

MOCK_UNSUCCESFUL_CONNECTION_STATE: Final = {"State": CONNECTION_STATE["Unavailable"]}
MOCK_UNSUCCESFUL_LOGIN_RESPONSE: Final = {""}

MOCK_USER_SETTINGS: Final = {"Id": "123"}

MOCK_ALBUM_NAME: Final = "MockAlbum"
MOCK_ALBUM_ID: Final = "MockAlbumId"

MOCK_ARTIST_NAME: Final = "MockArtist"
MOCK_ARTIST_ID: Final = "MockArtistId"

MOCK_TRACK_NAME: Final = "MockTrack"
MOCK_TRACK_ID: Final = "MockTrackId"

MOCK_TRACK: Final = {
    "Album": MOCK_ALBUM_NAME,
    "AlbumArtist": MOCK_ARTIST_NAME,
    "AlbumArtists": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST_NAME}],
    "AlbumId": MOCK_ALBUM_ID,
    "AlbumPrimaryImageTag": "MockPrimaryAlbumImage",
    "ArtistItems": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST_NAME}],
    "Artists": [MOCK_ARTIST_NAME],
    "Id": MOCK_TRACK_ID,
    "ImageTags": {"Primary": "MockPrimaryTrackImage"},
    "IndexNumber": 1,
    "IsFolder": False,
    "MediaSources": [
        {
            "Bitrate": 814217,
            "Container": "flac",
            "DefaultAudioStreamIndex": 0,
            "Formats": [],
            "GenPtsInput": False,
            "Id": "MockMediaSourceId",
            "IgnoreDts": False,
            "IgnoreIndex": False,
            "IsInfiniteStream": False,
            "IsRemote": False,
            "MediaAttachments": [],
            "MediaStreams": [
                {
                    "BitDepth": 16,
                    "ChannelLayout": "stereo",
                    "Channels": 2,
                    "Codec": "flac",
                    "CodecTimeBase": "1/44100",
                    "DisplayTitle": "FLAC - " "Stereo",
                    "Index": 0,
                    "IsDefault": False,
                    "IsExternal": False,
                    "IsForced": False,
                    "IsInterlaced": False,
                    "IsTextSubtitleStream": False,
                    "Level": 0,
                    "SampleRate": 44100,
                    "SupportsExternalStream": False,
                    "TimeBase": "1/44100",
                    "Type": "Audio",
                },
            ],
            "Name": "01 - Track - MockAlbum - MockArtist",
            "Path": "/media/music/MockArtist/MockAlbum/01 - Track - MockAlbum - MockArtist.flac",
            "Protocol": "File",
            "ReadAtNativeFramerate": False,
            "RequiredHttpHeaders": {},
            "RequiresClosing": False,
            "RequiresLooping": False,
            "RequiresOpening": False,
            "RunTimeTicks": 2954933248,
            "Size": 30074476,
            "SupportsDirectPlay": True,
            "SupportsDirectStream": True,
            "SupportsProbing": True,
            "SupportsTranscoding": True,
            "Type": "Default",
        }
    ],
    "MediaStreams": [
        {
            "BitDepth": 16,
            "ChannelLayout": "stereo",
            "Channels": 2,
            "Codec": "flac",
            "CodecTimeBase": "1/44100",
            "DisplayTitle": "FLAC - Stereo",
            "Index": 0,
            "IsDefault": False,
            "IsExternal": False,
            "IsForced": False,
            "IsInterlaced": False,
            "IsTextSubtitleStream": False,
            "Level": 0,
            "SampleRate": 44100,
            "SupportsExternalStream": False,
            "TimeBase": "1/44100",
            "Type": "Audio",
        },
    ],
    "MediaType": "Audio",
    "Name": MOCK_TRACK_NAME,
    "ParentId": MOCK_ALBUM_ID,
    "Path": "/media/music/MockArtist/MockAlbum/01 - Track - MockAlbum - MockArtist.flac",
    "ServerId": "MockServerId",
    "Type": "Audio",
}
