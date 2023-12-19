"""Tests for the services provided by the EnergyZero integration."""

import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.energyzero.const import DOMAIN
from homeassistant.components.energyzero.services import (
    ENERGY_SERVICE_NAME,
    GAS_SERVICE_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


@pytest.mark.usefixtures("init_integration")
async def test_has_services(
    hass: HomeAssistant,
) -> None:
    """Test the existence of the EnergyZero Service."""
    assert hass.services.has_service(DOMAIN, GAS_SERVICE_NAME)
    assert hass.services.has_service(DOMAIN, ENERGY_SERVICE_NAME)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [GAS_SERVICE_NAME, ENERGY_SERVICE_NAME])
@pytest.mark.parametrize("incl_vat", [{"incl_vat": False}, {"incl_vat": True}])
@pytest.mark.parametrize("start", [{"start": "2023-01-01 00:00:00"}, {}])
@pytest.mark.parametrize("end", [{"end": "2023-01-01 00:00:00"}, {}])
async def test_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    service: str,
    incl_vat: dict[str, bool],
    start: dict[str, str],
    end: dict[str, str],
) -> None:
    """Test the EnergyZero Service."""

    data = incl_vat | start | end

    assert snapshot == await hass.services.async_call(
        DOMAIN,
        service,
        data,
        blocking=True,
        return_response=True,
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [GAS_SERVICE_NAME, ENERGY_SERVICE_NAME])
@pytest.mark.parametrize(
    ("service_data", "error", "error_message"),
    [
        ({}, vol.er.Error, "required key not provided .+"),
        (
            {"incl_vat": "incorrect vat"},
            vol.er.Error,
            "expected bool for dictionary value .+",
        ),
        (
            {"incl_vat": True, "start": "incorrect date"},
            ServiceValidationError,
            "Invalid datetime provided.",
        ),
        (
            {"incl_vat": True, "end": "incorrect date"},
            ServiceValidationError,
            "Invalid datetime provided.",
        ),
    ],
)
async def test_service_validation(
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, str],
    error: type[Exception],
    error_message: str,
) -> None:
    """Test the EnergyZero Service validation."""

    with pytest.raises(error, match=error_message):
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data,
            blocking=True,
            return_response=True,
        )
