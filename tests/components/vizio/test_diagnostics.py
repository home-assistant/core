"""Tests for the Vizio diagnostics platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from vizaio import SystemVersions, VizioConnectionError

from homeassistant.core import HomeAssistant

from .conftest import setup_integration

MOCK_VERSIONS = SystemVersions(
    firmware="3.720.9.1-1",
    serial_number="fakeserial",
    esn="fakeesn",
    scpl="3.4.3-2614.0002",
    raw={
        "FIRMWARE": "3.720.9.1-1",
        "SERIAL NUMBER": "fakeserial",
        "ESN": "fakeesn",
        "SCPL": "3.4.3-2614.0002",
        "acr": "1.2.3",
    },
)


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tv_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics output."""
    with patch(
        "homeassistant.components.vizio.Vizio.get_versions",
        return_value=MOCK_VERSIONS,
    ):
        await setup_integration(hass, mock_tv_config_entry)
        diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, mock_tv_config_entry
        )

    assert diagnostics == snapshot


@pytest.mark.usefixtures("vizio_connect", "vizio_update")
async def test_diagnostics_versions_unavailable(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tv_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics degrade gracefully when the versions call fails."""
    with patch(
        "homeassistant.components.vizio.Vizio.get_versions",
        side_effect=VizioConnectionError("cannot connect"),
    ):
        await setup_integration(hass, mock_tv_config_entry)
        diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, mock_tv_config_entry
        )

    assert diagnostics["versions"] is None
    assert diagnostics["data"]["is_on"] is True
