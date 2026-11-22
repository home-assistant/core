"""Fast.com integration tests."""

from fastdotcom import FastClientInfo, FastLocation, FastSpeedtestResult, FastTarget

MOCK_DATA = FastSpeedtestResult(
    download_speed=100.0,
    upload_speed=50.0,
    unloaded_ping=15.2,
    loaded_ping=20.2,
    unloaded_pings=(15.0, 15.4),
    loaded_pings=(19.8, 20.6),
    bytes_downloaded=125_000_000,
    bytes_uploaded=62_500_000,
    client=FastClientInfo(
        ip="198.51.100.42",
        asn="64512",
        isp="Example Fiber",
        location=FastLocation(city="Madrid", country="ES"),
    ),
    targets=(
        FastTarget(
            url="https://oca.example.net/speedtest?t=secret",
            name="https://oca.example.net/speedtest?t=secret",
            location=FastLocation(city="Madrid", country="ES"),
        ),
    ),
    elapsed_seconds=10.5,
)
