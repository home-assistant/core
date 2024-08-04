"""The tests for evohome."""

from __future__ import annotations

import pytest

from homeassistant.components.evohome import DOMAIN
from homeassistant.components.evohome.const import EvoService
from homeassistant.core import HomeAssistant

from .conftest import setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_vendor_json(hass: HomeAssistant, install: str) -> None:
    """Test setup of a Honeywell TCC-compatible system."""

    await setup_evohome(hass, installation=install)

    num_entities = (
        TEST_INSTALLS[install].get("num_dhw", 0) + TEST_INSTALLS[install]["num_zones"]
    )

    assert len(hass.data["entity_info"].keys()) == num_entities + 1

    if "water_heater.domestic_hot_water" in hass.data["entity_info"]:
        assert TEST_INSTALLS[install].get("num_dhw", 0) == 1
    else:
        assert TEST_INSTALLS[install].get("num_dhw", 0) == 0

    domain_services = hass.services.async_services_for_domain(DOMAIN)
    assert len(domain_services) == TEST_INSTALLS[install].get(
        "num_svcs", len(EvoService)
    )
