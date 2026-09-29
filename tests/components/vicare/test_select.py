"""Test ViCare select entity."""

import logging
from unittest.mock import patch

import pytest
from PyViCare.PyViCareUtils import PyViCareRateLimitError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    fixtures: list[Fixture] = [
        Fixture({"type:heatpump"}, "vicare/Vitocal250A.json"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
        patch(f"{MODULE}.PLATFORMS", [Platform.SELECT]),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_api_error_logged_on_the_edge(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a lasting API error is logged once and again after it clears."""
    fixtures: list[Fixture] = [Fixture({"type:heatpump"}, "vicare/Vitocal250A.json")]
    vicare_data = MockPyViCare(fixtures).as_vicare_data()
    api = vicare_data.devices[0].api

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(f"{MODULE}._setup_vicare_api", return_value=vicare_data),
        patch(f"{MODULE}.PLATFORMS", [Platform.SELECT]),
    ):
        await setup_integration(hass, mock_config_entry)

    entity_id = hass.states.async_entity_ids(SELECT_DOMAIN)[0]
    error = PyViCareRateLimitError(
        {
            "extendedPayload": {
                "name": "DEVICE_COMMUNICATION_ERROR",
                "requestCountLimit": 1450,
                "limitReset": 1700000000000,
            }
        }
    )

    def logged() -> list[str]:
        return [
            record.getMessage()
            for record in caplog.records
            if record.levelno >= logging.WARNING
            and "rate limit exceeded" in record.getMessage()
        ]

    caplog.clear()
    with patch.object(api, "getDomesticHotWaterOperatingModes", side_effect=error):
        for _ in range(3):
            await async_update_entity(hass, entity_id)
    assert len(logged()) == 1

    await async_update_entity(hass, entity_id)
    with patch.object(api, "getDomesticHotWaterOperatingModes", side_effect=error):
        await async_update_entity(hass, entity_id)
    assert len(logged()) == 2
