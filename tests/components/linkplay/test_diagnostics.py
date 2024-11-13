"""Tests for the LinkPlay diagnostics."""

from unittest.mock import patch

from linkplay.bridge import LinkPlayMultiroom
from linkplay.consts import API_ENDPOINT
from linkplay.endpoint import LinkPlayApiEndpoint
from syrupy import SnapshotAssertion

from homeassistant.components.linkplay.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import HOST, mock_lp_aiohttp_client

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""

    with (
        mock_lp_aiohttp_client() as mock_session,
        patch.object(LinkPlayMultiroom, "update_status", return_value=None),
    ):
        endpoints = [
            LinkPlayApiEndpoint(protocol="https", endpoint=HOST, session=None),
            LinkPlayApiEndpoint(protocol="http", endpoint=HOST, session=None),
        ]
        for endpoint in endpoints:
            mock_session.get(
                API_ENDPOINT.format(str(endpoint), "getPlayerStatusEx"),
                text=load_fixture("getPlayerEx.json", DOMAIN),
            )

            mock_session.get(
                API_ENDPOINT.format(str(endpoint), "getStatusEx"),
                text=load_fixture("getStatusEx.json", DOMAIN),
            )

        await setup_integration(hass, mock_config_entry)

        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
            == snapshot
        )
