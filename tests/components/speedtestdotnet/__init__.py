"""Tests for SpeedTest."""

MOCK_SERVERS = {
    "*Auto Detect": "",
    "Server1": [{"id": "1"}],
    "Server2": [{"id": "2"}],
}

MOCK_RESULTS = {
    "download": 15698075.905353006,
    "upload": 2520647.0195683613,
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
