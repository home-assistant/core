"""Constants for the Jellyfin integration tests."""

from typing import Final

from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE

TEST_CONFIG_ENTRY_ID = "1"

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

MOCK_FOLDER: Final = "MockFolder"
MOCK_FOLDER_ID: Final = "MockFolderId"

MOCK_ALBUM_FOLDER: Final = "MockAlbumFolder"
MOCK_ALBUM_FOLDER_ID: Final = "MockAlbumFolderId"

MOCK_VIDEO_FOLDER: Final = "MockVideoFolder"
MOCK_VIDEO_FOLDER_ID: Final = "MockVideoFolderId"

MOCK_ARTIST_NAME: Final = "MockArtist"
MOCK_ARTIST_ID: Final = "MockArtistId"

MOCK_ALBUM_NAME: Final = "MockAlbum"
MOCK_ALBUM_ID: Final = "MockAlbumId"

MOCK_NO_INDEX_ALBUM_NAME: Final = "MockNoIndexAlbum"
MOCK_NO_INDEX_ALBUM_ID: Final = "MockNoIndexAlbumId"

MOCK_TRACK_NAME: Final = "MockTrack"
MOCK_TRACK_ID: Final = "MockTrackId"

MOCK_NO_INDEX_TRACK_NAME: Final = "MockTrackNoIndex"
MOCK_NO_INDEX_TRACK_ID: Final = "MockTrackIdNoIndex"

MOCK_NO_SOURCE_TRACK_NAME: Final = "MockNoSourceTrack"
MOCK_NO_SOURCE_TRACK_ID: Final = "MockNoSourceTrackId"

MOCK_INVALID_SOURCE_TRACK_NAME: Final = "MockInvalidSourceTrack"
MOCK_INVALID_SOURCE_TRACK_ID: Final = "MockInvalidSourceTrackId"

MOCK_MOVIE: Final = "MockMovie"
MOCK_MOVIE_ID: Final = "MockMovieId"


MOCK_ARTIST_LIBRARY: Final = {
    "Name": MOCK_FOLDER,
    "ServerId": "MockServer",
    "Id": MOCK_FOLDER_ID,
    "ChannelId": "null",
    "IsFolder": "true",
    "Type": "CollectionFolder",
    "CollectionType": "music",
    "ImageTags": None,
    "BackdropImageTags": [],
    "ImageBlurHashes": {"Primary": {"MockPrimaryImageTag": "MockPrimaryImage"}},
    "LocationType": "FileSystem",
}

MOCK_ALBUM_LIBRARY: Final = {
    "Name": MOCK_ALBUM_FOLDER,
    "ServerId": "MockServer",
    "Id": MOCK_ALBUM_FOLDER_ID,
    "ChannelId": "null",
    "IsFolder": "true",
    "Type": "CollectionFolder",
    "CollectionType": "music",
    "ImageTags": {},
    "BackdropImageTags": [],
    "LocationType": "FileSystem",
}

MOCK_VIDEO_LIBRARY: Final = {
    "Name": MOCK_VIDEO_FOLDER,
    "ServerId": "MockServer",
    "Id": MOCK_VIDEO_FOLDER_ID,
    "ChannelId": "null",
    "IsFolder": "true",
    "Type": "CollectionFolder",
    "CollectionType": "video",
    "ImageTags": None,
    "BackdropImageTags": [],
    "LocationType": "FileSystem",
}

MOCK_ARTIST: Final = {
    "AlbumCount": 1,
    "Id": MOCK_ARTIST_ID,
    "ImageTags": {
        "Logo": "MockLogo",
        "Primary": "MockPrimaryArtistImage",
    },
    "IsFolder": True,
    "Name": MOCK_ARTIST_NAME,
    "ParentId": MOCK_FOLDER_ID,
    "Path": "/media/music/MockArtist",
    "PrimaryImageAspectRatio": 1,
    "ServerId": "MockServerId",
    "Type": "MusicArtist",
}

MOCK_ALBUM: Final = {
    "AlbumArtist": MOCK_ARTIST,
    "AlbumArtists": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "Artists": [MOCK_ARTIST],
    "Id": MOCK_ALBUM_ID,
    "ImageTags": {},  # set to empty to test handling of missing images
    "IsFolder": True,
    "Name": MOCK_ALBUM_NAME,
    "PrimaryImageAspectRatio": 1,
    "ServerId": "MockServerId",
    "Type": "MusicAlbum",
}

MOCK_NO_INDEX_ALBUM: Final = {
    "AlbumArtist": MOCK_ARTIST,
    "AlbumArtists": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "Artists": [MOCK_ARTIST],
    "Id": MOCK_NO_INDEX_ALBUM_ID,
    "ImageTags": {},  # set to empty to test handling of missing images
    "IsFolder": True,
    "Name": MOCK_NO_INDEX_ALBUM_NAME,
    "PrimaryImageAspectRatio": 1,
    "ServerId": "MockServerId",
    "Type": "MusicAlbum",
}

MOCK_TRACK: Final = {
    "Album": MOCK_ALBUM,
    "AlbumArtist": MOCK_ARTIST,
    "AlbumArtists": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "AlbumId": MOCK_ALBUM_ID,
    "AlbumPrimaryImageTag": "MockPrimaryAlbumImage",
    "ArtistItems": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "Artists": [MOCK_ARTIST],
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

MOCK_NO_INDEX_TRACK: Final = {
    "Album": MOCK_ALBUM,
    "AlbumArtist": MOCK_ARTIST,
    "AlbumArtists": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "AlbumId": MOCK_ALBUM_ID,
    "AlbumPrimaryImageTag": "MockPrimaryAlbumImage",
    "ArtistItems": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "Artists": [MOCK_ARTIST],
    "Id": MOCK_NO_INDEX_TRACK_ID,
    "ImageTags": {"Primary": "MockPrimaryTrackImage"},
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
    "Name": MOCK_NO_INDEX_TRACK_NAME,
    "ParentId": MOCK_ALBUM_ID,
    "Path": "/media/music/MockArtist/MockAlbum/01 - Track - MockAlbum - MockArtist.flac",
    "ServerId": "MockServerId",
    "Type": "Audio",
}

MOCK_NO_SOURCE_TRACK: Final = {
    "Album": MOCK_ALBUM,
    "AlbumArtist": MOCK_ARTIST,
    "AlbumArtists": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "AlbumId": MOCK_ALBUM_ID,
    "AlbumPrimaryImageTag": "MockPrimaryAlbumImage",
    "ArtistItems": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "Artists": [MOCK_ARTIST],
    "Id": MOCK_NO_SOURCE_TRACK_ID,
    "ImageTags": {"Primary": "MockPrimaryTrackImage"},
    "IndexNumber": 1,
    "IsFolder": False,
    "MediaSources": [],
    "MediaStreams": [],
    "MediaType": "Audio",
    "Name": MOCK_NO_SOURCE_TRACK_NAME,
    "ParentId": MOCK_ALBUM_ID,
    "Path": "",
    "ServerId": "MockServerId",
    "Type": "Audio",
}

MOCK_INVALID_SOURCE_TRACK: Final = {
    "Album": MOCK_ALBUM,
    "AlbumArtist": MOCK_ARTIST,
    "AlbumArtists": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "AlbumId": MOCK_ALBUM_ID,
    "AlbumPrimaryImageTag": "MockPrimaryAlbumImage",
    "ArtistItems": [{"Id": MOCK_ARTIST_ID, "Name": MOCK_ARTIST}],
    "Artists": [MOCK_ARTIST],
    "Id": MOCK_INVALID_SOURCE_TRACK_ID,
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
            "Path": "/media/music/MockArtist/MockAlbum/01 - Track - MockAlbum - MockArtist",
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
    "Name": MOCK_INVALID_SOURCE_TRACK_NAME,
    "ParentId": MOCK_ALBUM_ID,
    "Path": "/media/music/MockArtist/MockAlbum/01 - InvalidSourceTrack - MockAlbum - MockArtist",
    "ServerId": "MockServerId",
    "Type": "Audio",
}


MOCK_VIDEO: Final = {
    "Id": MOCK_MOVIE_ID,
    "ImageTags": {"Primary": "MockPrimaryVideoImage"},
    "IsFolder": False,
    "MediaType": "Video",
    "Name": MOCK_MOVIE,
    "ParentId": MOCK_VIDEO_FOLDER_ID,
    "Path": "/media/movies/MockMovie.mkv ",
    "ServerId": "MockServerId",
    "Type": "Movie",
    "VideoType": "VideoFile",
}

MOCK_MEDIA_FOLDERS: Final = {"Items": [MOCK_ARTIST_LIBRARY]}
