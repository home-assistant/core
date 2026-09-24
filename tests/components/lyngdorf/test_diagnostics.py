"""Tests for the Lyngdorf diagnostics."""

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.lyngdorf.const import SSDP_ST
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the media player platform."""
    return [Platform.MEDIA_PLAYER]


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics output."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == snapshot(exclude=props("entry_id", "created_at", "modified_at"))


async def test_lipsync_range_reported_before_the_device_reports_a_value(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_receiver: MagicMock,
) -> None:
    """Test the lipsync range still reports before the first value arrives."""
    mock_receiver.lipsync = None

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )

    assert diagnostics["state"]["lipsync"] is None
    assert diagnostics["ranges"]["lipsync_range"] is not None


async def test_diagnostics_includes_ssdp_description(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the UPnP description is captured, with the serial redacted."""
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:864ab4c0-0fdb-46a7-84ad-aae23ee0d44f::upnp:rootdevice",
        ssdp_st=SSDP_ST,
        ssdp_udn="uuid:864ab4c0-0fdb-46a7-84ad-aae23ee0d44f",
        ssdp_location="http://127.0.0.1:55088/description.xml",
        upnp={
            "deviceType": "urn:schemas-upnp-org:device:MediaRenderer:2",
            "friendlyName": "Solar",
            "manufacturer": "Lyngdorf",
            "modelName": "MP-60",
            "serialNumber": "0050c27c76b2",
        },
    )

    with patch(
        "homeassistant.components.lyngdorf.diagnostics.async_get_discovery_info_by_st",
        return_value=[discovery],
    ):
        result = await get_diagnostics_for_config_entry(
            hass, hass_client, init_integration
        )

    assert result["ssdp"] == snapshot
