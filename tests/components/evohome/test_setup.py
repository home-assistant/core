"""The tests for evohome."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from homeassistant.components.evohome import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import ResultSet, expected_results_fixture, setup_evohome
from .const import TEST_INSTALLS

_LOGGER = logging.getLogger(__name__)


class ExpectedResults:
    """A class to hold the expected state of the evohome integration."""

    def __init__(self, hass: HomeAssistant, expected: ResultSet) -> None:
        """Initialize the database of expected states/services."""

        # will assert against hass.states, and hass.services
        self._hass = hass

        # expected entity states, services
        self.entities = {
            i: j for k in ("tcs", "zones", "dhw") for i, j in expected[k].items()
        }

        self.tcs = list(expected["tcs"].keys())[0]
        self.zones = list(expected["zones"].keys())
        if dhws := expected.get("dhw"):
            self.dhw = list(dhws.keys())[0]
        else:
            self.dhw = None

        # c.f. hass.services.async_services_for_domain(DOMAIN)
        self.services = expected["services"]

    def assert_entities(self) -> None:
        """Assert that the actual entity ids are as expected."""
        # c.f. hass.states.async_entity_ids().

        assert set(self._hass.states.async_entity_ids()) == set(self.entities)

    def assert_entity_state(self, entity_id: str) -> None:
        """Assert the entity was expected and state attrs match."""

        entity = self._hass.states.get(entity_id)

        try:
            for attr, value in self.entities[entity_id].items():
                try:
                    assert (
                        getattr(entity, attr) == value
                    ), f"{attr} is {entity.attributes[attr]}"

                except AttributeError:
                    assert (
                        entity.attributes[attr] == value
                    ), f"{attr} is {entity.attributes[attr]}"

        except AssertionError:
            _LOGGER.warning("Mocked state of %s is: %s", entity_id, self._state(entity))
            raise

    def _state(self, entity) -> dict[str, Any]:
        """Return the mocked state of the evohome entity."""

        expected = {
            "state": entity.state,
            "current_temperature": entity.attributes["current_temperature"],
            "supported_features": entity.attributes["supported_features"],
        }
        for k in ("away_mode", "operation_mode", "preset_mode"):
            if k in entity.attributes:
                expected[k] = entity.attributes[k]

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
