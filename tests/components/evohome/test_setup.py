"""The tests for evohome."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from homeassistant.components.evohome import DOMAIN
from homeassistant.core import HomeAssistant, State

from .conftest import expected_results_fixture, setup_evohome
from .const import TEST_INSTALLS

_LOGGER = logging.getLogger(__name__)


class ExpectedResults:
    """A class to hold the expected state of an evohome integration instance."""

    tcs: str  # entity_id of TCS, always exactly 1
    zones: list[str]  # entity_id of zones, 1 or more
    dhw: str | None  # entity_id of DHW, 0 or 1
    services: list[str]  # service names

    def __init__(self, hass: HomeAssistant, expected: dict[str, Any]) -> None:
        """Initialize the database of expected states/services."""

        self._hass = hass

        self.entities = {
            i: j for k in ("tcs", "zones", "dhw") for i, j in expected[k].items()
        }

        self.tcs = list(expected["tcs"].keys())[0]
        self.zones = list(expected["zones"].keys())
        if dhws := expected.get("dhw"):
            self.dhw = list(dhws.keys())[0]
        else:
            self.dhw = None

        self.services = expected["services"]

    def assert_entities(self) -> None:
        """Assert that the actual entity ids are as expected."""

        assert set(self._hass.states.async_entity_ids()) == set(self.entities)

    def assert_entity_state(self, entity_id: str) -> None:
        """Assert the entity was expected and selected state attrs match."""

        state = self._hass.states.get(entity_id)
        assert state is not None, f"Expected entity {entity_id} has no state"

        expected: dict = self.entities[entity_id]

        try:
            assert state.state == expected["state"], f"state is {state.state}"
            for attr, value in expected["attributes"].items():
                assert state.attributes[attr] == value

        except AssertionError:
            _LOGGER.warning(
                "Mocked state of %s is: %s", entity_id, self._serialize(state)
            )
            raise

    @staticmethod
    def _serialize(state: State) -> dict[str, Any]:
        expected: dict = {"state": state.state, "attributes": {}}

        for k in (
            "away_mode",
            "current_temperature",
            "operation_mode",
            "preset_mode",
            "supported_features",
        ):
            if k in state.attributes:
                expected["attributes"][k] = state.attributes[k]

        return expected

    def assert_services(self) -> None:
        """Assert the actual services are as expected."""

        assert set(self._hass.services.async_services_for_domain(DOMAIN)) == set(
            self.services
        )


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_vendor_json(hass: HomeAssistant, install: str) -> None:
    """Test setup of a Honeywell TCC-compatible system."""

    await setup_evohome(hass, installation=install)

    results = ExpectedResults(hass, expected_results_fixture(install))

    results.assert_services()
    results.assert_entities()

    for entity_id in results.entities:
        results.assert_entity_state(entity_id)
