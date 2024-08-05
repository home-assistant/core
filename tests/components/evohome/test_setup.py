"""The tests for evohome."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant

from .conftest import ExpectedResults, expected_results_fixture, setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_vendor_json(hass: HomeAssistant, install: str) -> None:
    """Test setup of a Honeywell TCC-compatible system."""

    await setup_evohome(hass, installation=install)

    results = ExpectedResults(hass, expected_results_fixture(install))

    results.assert_services()
    results.assert_entities()

    for entity_id in results.entities:
        results.assert_entity_state(entity_id)
