"""Test samsungtv diagnostics."""

from unittest.mock import Mock

import pytest
from samsungtvws.exceptions import HttpApiError
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_samsungtv_entry
from .const import ENTRYDATA_ENCRYPTED_WEBSOCKET, ENTRYDATA_WEBSOCKET

from tests.common import load_json_object_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("remote_websocket", "rest_api")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry = await setup_samsungtv_entry(hass, ENTRYDATA_WEBSOCKET)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=props("created_at", "modified_at"))


@pytest.mark.usefixtures("remote_encrypted_websocket")
async def test_entry_diagnostics_encrypted(
    hass: HomeAssistant,
    rest_api: Mock,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    rest_api.rest_device_info.return_value = load_json_object_fixture(
        "device_info_UE48JU6400.json", DOMAIN
    )
    config_entry = await setup_samsungtv_entry(hass, ENTRYDATA_ENCRYPTED_WEBSOCKET)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=props("created_at", "modified_at"))


@pytest.mark.usefixtures("remote_encrypted_websocket")
async def test_entry_diagnostics_encrypte_offline(
    hass: HomeAssistant,
    rest_api: Mock,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    rest_api.rest_device_info.side_effect = HttpApiError
    config_entry = await setup_samsungtv_entry(hass, ENTRYDATA_ENCRYPTED_WEBSOCKET)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=props("created_at", "modified_at"))
