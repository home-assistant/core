"""Tests for the services provided by the easyEnergy integration."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.easyenergy.const import DOMAIN
from homeassistant.components.easyenergy.services import (
    ENERGY_RETURN_SERVICE_NAME,
    ENERGY_USAGE_SERVICE_NAME,
    GAS_SERVICE_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


@pytest.mark.usefixtures("init_integration")
async def test_has_services(
    hass: HomeAssistant,
) -> None:
    """Test the existence of the easyEnergy Service."""
    assert hass.services.has_service(DOMAIN, GAS_SERVICE_NAME)
    assert hass.services.has_service(DOMAIN, ENERGY_USAGE_SERVICE_NAME)
    assert hass.services.has_service(DOMAIN, ENERGY_RETURN_SERVICE_NAME)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "service", [GAS_SERVICE_NAME, ENERGY_USAGE_SERVICE_NAME, ENERGY_RETURN_SERVICE_NAME]
)
@pytest.mark.parametrize("incl_vat", [{"incl_vat": False}, {"incl_vat": True}, {}])
@pytest.mark.parametrize(
    "start", [{"start": "2023-01-01 00:00:00"}, {"start": "incorrect date"}, {}]
)
@pytest.mark.parametrize(
    "end", [{"end": "2023-01-01 00:00:00"}, {"end": "incorrect date"}, {}]
)
async def test_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    service: str,
    incl_vat: dict[str, bool],
    start: dict[str, str],
    end: dict[str, str],
) -> None:
    """Test the easyEnergy Service."""

    data = incl_vat | start | end

    try:
        response = await hass.services.async_call(
            DOMAIN,
            service,
            data,
            blocking=True,
            return_response=True,
        )
        assert response == snapshot
    except ServiceValidationError as e:
        assert e == snapshot
