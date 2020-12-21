"""Transmission service platform tests."""
from tests.async_mock import patch


async def test_call_services(hass, torrent_info):
    """Test that the Transmission services are called."""
    with patch(
        "homeassistant.components.transmission.transmissionrpc.Client.add_torrent"
    ):
        assert await (
            hass.services.async_call(
                "transmission",
                "add_torrent",
                service_data={"name": "Transmission", "torrent": "magnet:"},
                blocking=True,
            )
        )
        assert await (
            hass.services.async_call(
                "transmission",
                "add_torrent",
                service_data={"name": "Transmission", "torrent": "blumber"},
                blocking=True,
            )
        )

    with patch(
        "homeassistant.components.transmission.transmissionrpc.Client.remove_torrent"
    ):
        assert await (
            hass.services.async_call(
                "transmission",
                "remove_torrent",
                service_data={"name": "Transmission", "id": 1},
                blocking=True,
            )
        )
