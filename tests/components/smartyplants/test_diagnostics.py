"""Tests for the diagnostics provided by the SmartyPlants integration."""

from typing import Any
from unittest.mock import AsyncMock

from pysmartyplants import SmartyPlantsConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smartyplants.const import CONF_WEBHOOK_SECRET, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import ACCOUNT_ID, API_KEY, WEBHOOK_ID, WEBHOOK_SECRET


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


async def test_diagnostics_without_coordinator(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_smartyplants_client: AsyncMock,
) -> None:
    """Test an entry waiting to retry setup still downloads."""
    mock_smartyplants_client.async_get_sensors.side_effect = (
        SmartyPlantsConnectionError("boom")
    )

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["webhook_configured"] is True
    assert "sensors" not in diagnostics
    assert API_KEY not in str(diagnostics)


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_diagnostics_reports_unregistered_webhook(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a secret with no webhook id is not reported as configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SmartyPlants",
        data={CONF_API_KEY: API_KEY, CONF_WEBHOOK_SECRET: WEBHOOK_SECRET},
        unique_id=ACCOUNT_ID,
    )

    await setup_integration(hass, entry)

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["webhook_configured"] is False
