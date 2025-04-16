"""Constants for Snapcast tests."""

TEST_CLIENT_ENTITY_ID = "media_player.test_client_snapcast_client"
TEST_GROUP_ENTITY_ID = "media_player.test_group_snapcast_group"

TEST_STATE = {
    "server": {
        "server": {
            "snapserver": {
                "controlProtocolVersion": 1,
                "name": "Snapserver",
                "protocolVersion": 1,
                "version": "0.10.0",
            },
        },
        "groups": [
            {
                "clients": [
                    {
                        "id": "00:21:6a:7d:74:fc#2",
                        "connected": True,
                        "lastSeen": {"sec": 1488025751, "usec": 654777},
                        "config": {
                            "instance": 2,
                            "latency": 6,
                            "name": "test_client",
                            "volume": {"muted": False, "percent": 48},
                        },
                        "snapclient": {
                            "name": "Snapclient",
                            "protocolVersion": 2,
                            "version": "0.10.0",
                        },
                    }
                ],
                "id": "4dcc4e3b-c699-a04b-7f0c-8260d23c43e1",
                "muted": False,
                "name": "test_group",
                "stream_id": "test_stream_1",
            }
        ],
        "streams": [
            {
                "id": "test_stream_1",
                "status": "playing",
                "uri": {
                    "fragment": "",
                    "host": "",
                    "query": {
                        "chunk_ms": "20",
                        "codec": "flac",
                        "name": "Test Stream 1",
                        "sampleformat": "48000:16:2",
                    },
                    "scheme": "pipe",
                },
                "properties": {
                    "position": 30.0,
                    "metadata": {
                        "album": "Test Album",
                        "artist": ["Test Artist 1", "Test Artist 2"],
                        "title": "Test Title",
                        "artUrl": "http://localhost/test_art.jpg",
                        "albumArtist": ["Test Album Artist 1", "Test Album Artist 2"],
                        "trackNumber": 10,
                        "duration": 60.0,
                    },
                },
            },
            {
                "id": "test_stream_2",
                "status": "idle",
                "uri": {
                    "fragment": "",
                    "host": "",
                    "query": {
                        "chunk_ms": "20",
                        "codec": "flac",
                        "name": "Test Stream 2",
                        "sampleformat": "48000:16:2",
                    },
                    "scheme": "pipe",
                },
            },
        ],
    }
}
