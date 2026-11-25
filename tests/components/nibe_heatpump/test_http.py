"""Test the Nibe Heat Pump HTTP views."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from nibe.heatpump import Model
import pytest
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.http.auth import async_sign_path
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import async_add_entry, async_add_model

MOCK_MODBUS_ENTRY_DATA = {
    "model": "F1155",
    "modbus_url": "tcp://127.0.0.1",
    "modbus_unit": 0,
    "connection_type": "modbus",
}


@pytest.fixture(autouse=True)
async def fixture_platforms():
    """Only load platforms without model specific logic."""
    with patch(
        "homeassistant.components.nibe_heatpump.PLATFORMS",
        [Platform.NUMBER, Platform.SENSOR],
    ):
        yield


@pytest.mark.freeze_time("2026-11-14 12:00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_log_set_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    coils: dict[int, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test downloading a LOG.SET of the coils in use, read only coils first."""
    coils.update({40004: 20.0, 43005: 1234, 43420: 100, 47011: 1})
    entry = await async_add_model(hass, Model.F1155)

    resp = await (await hass_client()).get(
        f"/api/nibe_heatpump/{entry.entry_id}/log_set"
    )
    assert resp.status == HTTPStatus.OK
    assert resp.headers["Content-Disposition"] == 'attachment; filename="LOG.SET"'
    assert await resp.read() == snapshot


async def test_log_set_signed_path(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test a LOG.SET link signed for an admin works without an auth header."""
    entry = await async_add_model(hass, Model.F1155)
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    assert refresh_token
    path = async_sign_path(
        hass,
        f"/api/nibe_heatpump/{entry.entry_id}/log_set",
        timedelta(minutes=5),
        refresh_token_id=refresh_token.id,
    )

    resp = await (await hass_client_no_auth()).get(path)
    assert resp.status == HTTPStatus.OK


async def test_log_set_requires_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test the LOG.SET is refused for users that are not admins."""
    entry = await async_add_model(hass, Model.F1155)

    client = await hass_client(hass_read_only_access_token)
    resp = await client.get(f"/api/nibe_heatpump/{entry.entry_id}/log_set")
    assert resp.status == HTTPStatus.UNAUTHORIZED


async def test_log_set_not_supported(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test there is no LOG.SET for Modbus connections."""
    entry = await async_add_entry(hass, MOCK_MODBUS_ENTRY_DATA)

    resp = await (await hass_client()).get(
        f"/api/nibe_heatpump/{entry.entry_id}/log_set"
    )
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_log_set_unknown_entry(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test there is no LOG.SET for unknown entries."""
    await async_add_model(hass, Model.F1155)

    resp = await (await hass_client()).get("/api/nibe_heatpump/unknown/log_set")
    assert resp.status == HTTPStatus.NOT_FOUND
