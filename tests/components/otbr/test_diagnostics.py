"""Tests for the OpenThread Border Router diagnostics."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from python_otbr_api import ActiveDataSet, OTBRError
from python_otbr_api.models import SecurityPolicy, Timestamp
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

ACTIVE_DATASET = ActiveDataSet(
    active_timestamp=Timestamp(authoritative=False, seconds=1, ticks=0),
    channel_mask=134215680,
    channel=15,
    extended_pan_id="f642646da209b1d0",
    mesh_local_prefix="fdf5:7b5a:fe2:aaf6::/64",
    network_key="de98b5ba1a528fee049d4b4b01835375",
    network_name="OpenThread HA",
    pan_id=9636,
    psk_c="f5dd18371bfd29e1a601ef6ffad94c03",
    security_policy=SecurityPolicy(rotation_time=672, routers=True),
)


# The timeout patch must be active before the entry fixture starts discovery
@pytest.mark.usefixtures("fast_border_agent_discovery", "otbr_config_entry_thread")
@pytest.mark.parametrize(
    "coprocessor_version_side_effect",
    [
        pytest.param(None, id="coprocessor_version"),
        pytest.param(OTBRError, id="no_coprocessor_version"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    get_coprocessor_version: AsyncMock,
    coprocessor_version_side_effect: type[Exception] | None,
) -> None:
    """Test config entry diagnostics."""
    get_coprocessor_version.side_effect = coprocessor_version_side_effect
    config_entry = hass.config_entries.async_entries("otbr")[0]
    with (
        patch("python_otbr_api.OTBR.get_active_dataset", return_value=ACTIVE_DATASET),
        patch("python_otbr_api.OTBR.get_api_version", return_value="1.0.0"),
        patch("python_otbr_api.OTBR.get_pending_dataset_tlvs", return_value=None),
    ):
        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
            == snapshot
        )
