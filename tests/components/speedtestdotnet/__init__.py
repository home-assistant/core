"""Tests for SpeedTest."""

MOCK_SERVERS = {
    1: [
        {
            "url": "http://server_1:8080/speedtest/upload.php",
            "lat": "1",
            "lon": "1",
            "name": "Server1",
            "country": "Country1",
            "cc": "LL1",
            "sponsor": "Sponsor1",
            "id": "1",
            "host": "server1:8080",
            "d": 1,
        }
    ],
    2: [
        {
            "url": "http://server_2:8080/speedtest/upload.php",
            "lat": "2",
            "lon": "2",
            "name": "Server2",
            "country": "Country2",
            "cc": "LL2",
            "sponsor": "Sponsor2",
            "id": "2",
            "host": "server2:8080",
            "d": 2,
        }
    ],
}

MOCK_RESULTS = {
    "download": 1024000,
    "upload": 1024000,
    "ping": 18.465,
    "server": {
        "url": "http://test_server:8080/speedtest/upload.php",
        "lat": "00.0000",
        "lon": "11.1111",
        "name": "NAME",
        "country": "Country",
        "id": "8408",
        "host": "test_server:8080",
        "d": 1.4858909757493415,
        "latency": 18.465,
    },
    "timestamp": "2020-05-29T07:28:57.908387Z",
    "bytes_sent": 4194304,
    "bytes_received": 19712300,
    "share": None,
}

MOCK_STATES = {"ping": "18", "download": "1.02", "upload": "1.02"}
