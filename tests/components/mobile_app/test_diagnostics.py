"""Tests for the Mobile App diagnostics."""

from http import HTTPStatus

from aiohttp.test_utils import TestClient
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mobile_app.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import REGISTER_CLEARTEXT


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    webhook_client: TestClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    reg_resp = await webhook_client.post(
        "/api/mobile_app/registrations",
        json={
            **REGISTER_CLEARTEXT,
            "app_data": {
                "push_url": "http://localhost/mock-push",
                "push_token": "abcd",
                "push_websocket_channel": True,
            },
        },
    )
    assert reg_resp.status == HTTPStatus.CREATED
    webhook_id = (await reg_resp.json())["webhook_id"]

    for sensor_type, unique_id in (
        ("sensor", "battery_level"),
        ("sensor", "battery_state"),
        ("binary_sensor", "is_charging"),
    ):
        resp = await webhook_client.post(
            f"/api/webhook/{webhook_id}",
            json={
                "type": "register_sensor",
                "data": {
                    "name": unique_id,
                    "state": 1,
                    "type": sensor_type,
                    "unique_id": unique_id,
                },
            },
        )
        assert resp.status == HTTPStatus.CREATED
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
