"""Tests for the services provided by the EnergyZero integration."""

import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.energyzero.const import DOMAIN
from homeassistant.components.energyzero.services import (
    ATTR_CONFIG_ENTRY,
    ENERGY_SERVICE_NAME,
    GAS_SERVICE_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


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
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    service: str,
    incl_vat: dict[str, bool],
    start: dict[str, str],
    end: dict[str, str],
) -> None:
    """Test the EnergyZero Service."""
    entry = {ATTR_CONFIG_ENTRY: mock_config_entry.entry_id}

    data = entry | incl_vat | start | end

    assert snapshot == await hass.services.async_call(
        DOMAIN,
        service,
        data,
        blocking=True,
        return_response=True,
    )


@pytest.fixture
def config_entry_data(
    mock_config_entry: MockConfigEntry, request: pytest.FixtureRequest
) -> dict[str, str]:
    """Fixture for the config entry."""
    if "config_entry" in request.param and request.param["config_entry"] is True:
        return {"config_entry": mock_config_entry.entry_id}

    return request.param


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [GAS_SERVICE_NAME, ENERGY_SERVICE_NAME])
@pytest.mark.parametrize(
    ("config_entry_data", "service_data", "error", "error_message"),
    [
        ({}, {}, vol.er.Error, "required key not provided .+"),
        (
            {"config_entry": True},
            {},
            vol.er.Error,
            "required key not provided .+",
        ),
        (
            {},
            {"incl_vat": True},
            vol.er.Error,
            "required key not provided .+",
        ),
        (
            {"config_entry": True},
            {"incl_vat": "incorrect vat"},
            vol.er.Error,
            "expected bool for dictionary value .+",
        ),
        (
            {"config_entry": "incorrect entry"},
            {"incl_vat": True},
            ServiceValidationError,
            "Invalid config entry.+",
        ),
        (
            {"config_entry": True},
            {
                "incl_vat": True,
                "start": "incorrect date",
            },
            ServiceValidationError,
            "Invalid datetime provided.",
        ),
        (
            {"config_entry": True},
            {
                "incl_vat": True,
                "end": "incorrect date",
            },
            ServiceValidationError,
            "Invalid datetime provided.",
        ),
    ],
    indirect=["config_entry_data"],
)
async def test_service_validation(
    hass: HomeAssistant,
    service: str,
    config_entry_data: dict[str, str],
    service_data: dict[str, str],
    error: type[Exception],
    error_message: str,
) -> None:
    """Test the EnergyZero Service validation."""

    with pytest.raises(error, match=error_message):
        await hass.services.async_call(
            DOMAIN,
            service,
            config_entry_data | service_data,
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [GAS_SERVICE_NAME, ENERGY_SERVICE_NAME])
async def test_service_called_with_unloaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test service calls with unloaded config entry."""

    await mock_config_entry.async_unload(hass)

    data = {"config_entry": mock_config_entry.entry_id, "incl_vat": True}

    with pytest.raises(
        ServiceValidationError, match=f"{mock_config_entry.title} is not loaded"
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            data,
            blocking=True,
            return_response=True,
        )
