"""Transmission service platform tests."""
from tests.common import patch


async def call_service(
    hass,
    ha_service_name,
    additional_service_data=None,
):
    """Test Transmission service."""
    service_data = {"name": "Transmission"}
    if additional_service_data:
        service_data.update(additional_service_data)
    service_call = await hass.services.async_call(
        "transmission",
        ha_service_name,
        service_data=service_data,
        blocking=True,
    )
    assert service_call


async def test_call_services(hass, torrent_info):
    """Test that the Transmission services are called."""
    with patch("transmissionrpc.Client.add_torrent"):
        await call_service(hass, "add_torrent", {"torrent": "magnet:"})
        await call_service(hass, "add_torrent", {"torrent": "blumber"})

    with patch("transmissionrpc.Client.remove_torrent"):
        await call_service(hass, "remove_torrent", {"id": 1})
