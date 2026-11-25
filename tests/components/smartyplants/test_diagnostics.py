"""Tests for the diagnostics provided by the SmartyPlants integration."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import API_KEY, WEBHOOK_ID, WEBHOOK_SECRET


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics payload."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_diagnostics_redacts_account_details(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    sensor_payloads: list[dict[str, Any]],
) -> None:
    """Test nothing identifying the account survives into the payload."""
    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    secrets = (
        API_KEY,
        WEBHOOK_ID,
        WEBHOOK_SECRET,
        sensor_payloads[0]["identifier"],
        sensor_payloads[0]["plant"]["imageUrl"],
    )
    rendered = str(diagnostics)
    for secret in secrets:
        assert secret not in rendered

    # The readings and the plant's own name are what make the file useful.
    assert sensor_payloads[0]["plant"]["name"] in rendered
    assert diagnostics["sensors"][0]["readings"]["temperature"]["value"] == 22.5
