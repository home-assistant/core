"""Tests for the services provided by the EnergyZero integration."""

from datetime import date
import re
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from energyzero import EnergyZeroNoDataError, PriceType
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

pytestmark = pytest.mark.freeze_time("2026-04-10 20:32:59")


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


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "incl_vat", "expected_price_type"),
    [
        (GAS_SERVICE_NAME, True, PriceType.MARKET_WITH_VAT),
        (GAS_SERVICE_NAME, False, PriceType.MARKET),
        (ENERGY_SERVICE_NAME, True, PriceType.MARKET_WITH_VAT),
        (ENERGY_SERVICE_NAME, False, PriceType.MARKET),
    ],
)
async def test_service_price_type_mapping(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    incl_vat: bool,
    expected_price_type: PriceType,
) -> None:
    """Test incl_vat maps to the expected EnergyZero price type."""
    await hass.services.async_call(
        DOMAIN,
        service,
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
            "incl_vat": incl_vat,
        },
        blocking=True,
        return_response=True,
    )

    method = (
        mock_energyzero.get_gas_prices
        if service == GAS_SERVICE_NAME
        else mock_energyzero.get_electricity_prices
    )
    assert method.await_args.kwargs["price_type"] is expected_price_type
    assert method.await_args.kwargs["local_tz"] == ZoneInfo(hass.config.time_zone)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [GAS_SERVICE_NAME, ENERGY_SERVICE_NAME])
async def test_service_dates_normalized_to_hass_timezone(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test service input datetimes are normalized to the HA timezone."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")

    await hass.services.async_call(
        DOMAIN,
        service,
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
            "incl_vat": True,
            "start": "2023-01-01 23:30:00-01:00",
        },
        blocking=True,
        return_response=True,
    )

    method = (
        mock_energyzero.get_gas_prices
        if service == GAS_SERVICE_NAME
        else mock_energyzero.get_electricity_prices
    )
    assert method.await_args.kwargs["start_date"] == date(2023, 1, 2)
    assert method.await_args.kwargs["local_tz"] == ZoneInfo("Europe/Amsterdam")


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
            "Invalid date provided. Got incorrect date",
        ),
        (
            {"config_entry": True},
            {
                "incl_vat": True,
                "end": "incorrect date",
            },
            ServiceValidationError,
            "Invalid date provided. Got incorrect date",
        ),
        (
            {"config_entry": True},
            {
                "incl_vat": True,
                "start": "2023-01-01 00:00:00",
                "end": "2023-01-02 00:00:00",
            },
            ServiceValidationError,
            "Invalid date range provided. Start 2023-01-01 and end 2023-01-02 must be on the same day",
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

    with pytest.raises(error) as exc:
        await hass.services.async_call(
            DOMAIN,
            service,
            config_entry_data | service_data,
            blocking=True,
            return_response=True,
        )
    assert re.match(error_message, str(exc.value))


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [GAS_SERVICE_NAME, ENERGY_SERVICE_NAME])
async def test_service_called_with_unloaded_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test service calls with unloaded config entry."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

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


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("service", [GAS_SERVICE_NAME, ENERGY_SERVICE_NAME])
async def test_service_no_data_returns_validation_error(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
) -> None:
    """Test backend no-data errors are surfaced as service validation errors."""
    method = (
        mock_energyzero.get_gas_prices
        if service == GAS_SERVICE_NAME
        else mock_energyzero.get_electricity_prices
    )
    method.side_effect = EnergyZeroNoDataError(
        "not found: prices do not span the whole requested date"
    )

    with pytest.raises(
        ServiceValidationError,
        match=r"No price data available for 2026-04-10\.?",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            {
                ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
                "incl_vat": True,
            },
            blocking=True,
            return_response=True,
        )
