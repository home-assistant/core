"""Tests for the services provided by the EnergyZero integration."""

from datetime import UTC, date, datetime, timedelta
import re
from unittest.mock import AsyncMock, call
from zoneinfo import ZoneInfo

from energyzero import EnergyPrices, EnergyZeroNoDataError, Interval, PriceType
from energyzero.models import TimeRange
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.energyzero.const import (
    CONF_ELECTRICITY_PRICE_INTERVAL,
    DOMAIN,
)
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
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            GAS_SERVICE_NAME,
            {"incl_vat": False},
        ),
        (
            ENERGY_SERVICE_NAME,
            {"incl_vat": True},
        ),
    ],
)
async def test_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    service: str,
    service_data: dict[str, str | bool],
) -> None:
    """Test the EnergyZero Service."""
    data = {ATTR_CONFIG_ENTRY: mock_config_entry.entry_id} | service_data

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
            "end": "2023-01-02 00:30:00-01:00",
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


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "expected_prices"),
    [
        (
            GAS_SERVICE_NAME,
            [
                {
                    "price": 0.45193447944,
                    "timestamp": "2026-04-10 04:00:00+00:00",
                }
            ],
        ),
        (
            ENERGY_SERVICE_NAME,
            [
                {"price": 0.12572, "timestamp": "2026-04-10 21:00:00+00:00"},
                {"price": 0.125925, "timestamp": "2026-04-10 22:00:00+00:00"},
                {"price": 0.1120525, "timestamp": "2026-04-10 23:00:00+00:00"},
            ],
        ),
    ],
)
async def test_service_filters_datetime_range(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    expected_prices: list[dict[str, str | float]],
) -> None:
    """Test services request each day and filter to the datetime range."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    mock_energyzero.reset_mock()

    response = await hass.services.async_call(
        DOMAIN,
        service,
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
            "incl_vat": False,
            "start": "2026-04-10 23:00:00+02:00",
            "end": "2026-04-11 02:00:00+02:00",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"prices": expected_prices}

    method = (
        mock_energyzero.get_gas_prices
        if service == GAS_SERVICE_NAME
        else mock_energyzero.get_electricity_prices
    )
    assert [item.kwargs["start_date"] for item in method.await_args_list] == [
        date(2026, 4, 10),
        date(2026, 4, 11),
    ]
    assert all(
        item.kwargs["end_date"] == item.kwargs["start_date"]
        for item in method.await_args_list
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
        ({}, {}, vol.error.Error, "required key not provided .+"),
        (
            {"config_entry": True},
            {},
            vol.error.Error,
            "required key not provided .+",
        ),
        (
            {},
            {"incl_vat": True},
            vol.error.Error,
            "required key not provided .+",
        ),
        (
            {"config_entry": True},
            {"incl_vat": "incorrect vat"},
            vol.error.Error,
            "expected bool at .+",
        ),
        (
            {"config_entry": "incorrect entry"},
            {"incl_vat": True},
            ServiceValidationError,
            ".+ config entry with ID incorrect entry was not found",
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
                "start": "2023-01-02",
                "end": "2023-01-01",
            },
            ServiceValidationError,
            "Invalid date range provided. End 2023-01-01 must be after start 2023-01-02",
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
        ServiceValidationError,
        match=f"{mock_config_entry.title} for integration energyzero is not loaded",
    ):
        await hass.services.async_call(
            DOMAIN,
            service,
            data,
            blocking=True,
            return_response=True,
        )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (GAS_SERVICE_NAME, {}),
        (ENERGY_SERVICE_NAME, {}),
        (ENERGY_SERVICE_NAME, {"price_type": "all_in", "interval": "quarter"}),
    ],
)
async def test_service_no_data_returns_validation_error(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, str],
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
                **service_data,
            },
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("entity_interval", ["hourly", "quarter_hourly"])
@pytest.mark.parametrize(
    ("interval_data", "expected_interval"),
    [
        pytest.param({}, Interval.HOUR, id="default-hour"),
        pytest.param({"interval": "hour"}, Interval.HOUR, id="hour"),
        pytest.param({"interval": "quarter"}, Interval.QUARTER, id="quarter"),
    ],
)
@pytest.mark.parametrize(
    ("price_data", "incl_vat", "expected_price_type"),
    [
        pytest.param({}, True, PriceType.MARKET_WITH_VAT, id="default-vat"),
        pytest.param({}, False, PriceType.MARKET, id="default-no-vat"),
        pytest.param(
            {"price_type": "market"}, True, PriceType.MARKET_WITH_VAT, id="market-vat"
        ),
        pytest.param(
            {"price_type": "market"}, False, PriceType.MARKET, id="market-no-vat"
        ),
        pytest.param({"price_type": "all_in"}, True, PriceType.ALL_IN, id="all-in-vat"),
        pytest.param(
            {"price_type": "all_in"},
            False,
            PriceType.ALL_IN_EXCL_VAT,
            id="all-in-no-vat",
        ),
    ],
)
async def test_energy_service_options(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_interval: str,
    interval_data: dict[str, str],
    expected_interval: Interval,
    price_data: dict[str, str],
    incl_vat: bool,
    expected_price_type: PriceType,
) -> None:
    """Action options and defaults are independent of entity configuration."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ELECTRICITY_PRICE_INTERVAL: entity_interval}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    coordinator_data = coordinator.data
    entity_states = hass.states.async_all()
    mock_energyzero.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
            "incl_vat": incl_vat,
            **price_data,
            **interval_data,
        },
        blocking=True,
        return_response=True,
    )

    mock_energyzero.get_electricity_prices.assert_awaited_once_with(
        start_date=date(2026, 4, 10),
        end_date=date(2026, 4, 10),
        interval=expected_interval,
        price_type=expected_price_type,
        local_tz=ZoneInfo(hass.config.time_zone),
    )
    mock_energyzero.get_gas_prices.assert_not_awaited()
    assert coordinator.data is coordinator_data
    assert hass.states.async_all() == entity_states
    assert mock_config_entry.options == {
        CONF_ELECTRICITY_PRICE_INTERVAL: entity_interval
    }


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("start", "end", "first_timestamp", "period_count"),
    [
        pytest.param(
            "2026-04-10", "2026-04-10", "2026-04-09T22:00:00+00:00", 96, id="date-only"
        ),
        pytest.param(
            "2026-04-10 00:07:00",
            "2026-04-10 00:38:00",
            "2026-04-09T22:00:00+00:00",
            3,
            id="partial-periods",
        ),
        pytest.param(
            "2026-04-10 00:15:00",
            "2026-04-10 00:30:00",
            "2026-04-09T22:15:00+00:00",
            1,
            id="exact-boundaries",
        ),
        pytest.param(
            "2026-04-10 23:53:00+02:00",
            "2026-04-11 00:07:00+02:00",
            "2026-04-10T21:45:00+00:00",
            2,
            id="multiple-days",
        ),
        pytest.param(
            "2026-03-29", "2026-03-29", "2026-03-28T23:00:00+00:00", 92, id="spring-dst"
        ),
        pytest.param(
            "2026-10-25",
            "2026-10-25",
            "2026-10-24T22:00:00+00:00",
            100,
            id="autumn-dst",
        ),
        pytest.param(
            "2026-03-29 01:53:00+01:00",
            "2026-03-29 03:07:00+02:00",
            "2026-03-29T00:45:00+00:00",
            2,
            id="spring-overlap",
        ),
        pytest.param(
            "2026-10-25 02:53:00+02:00",
            "2026-10-25 02:07:00+01:00",
            "2026-10-25T00:45:00+00:00",
            2,
            id="autumn-overlap",
        ),
    ],
)
async def test_energy_service_quarter_ranges(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    start: str,
    end: str,
    first_timestamp: str,
    period_count: int,
) -> None:
    """Filter actual quarter-hour ranges, including partial periods and DST."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    local_tz = ZoneInfo(hass.config.time_zone)
    first_day = date.fromisoformat(start[:10])
    last_day = date.fromisoformat(end[:10])
    days = [
        first_day + timedelta(days=index)
        for index in range((last_day - first_day).days + 1)
    ]
    step = timedelta(minutes=15)
    datasets = []
    for day in days:
        day_start = datetime.combine(day, datetime.min.time(), local_tz).astimezone(UTC)
        day_end = datetime.combine(
            day + timedelta(days=1), datetime.min.time(), local_tz
        ).astimezone(UTC)
        datasets.append(
            EnergyPrices(
                prices={
                    TimeRange(
                        day_start + index * step, day_start + (index + 1) * step
                    ): 0.25
                    for index in range((day_end - day_start) // step)
                },
                average_price=0.25,
            )
        )
    mock_energyzero.reset_mock()
    mock_energyzero.get_electricity_prices.side_effect = datasets

    response = await hass.services.async_call(
        DOMAIN,
        ENERGY_SERVICE_NAME,
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
            "incl_vat": True,
            "price_type": "all_in",
            "interval": "quarter",
            "start": start,
            "end": end,
        },
        blocking=True,
        return_response=True,
    )

    first = datetime.fromisoformat(first_timestamp)
    assert response == {
        "prices": [
            {"price": 0.25, "timestamp": str(first + index * step)}
            for index in range(period_count)
        ]
    }
    assert mock_energyzero.get_electricity_prices.await_args_list == [
        call(
            start_date=day,
            end_date=day,
            interval=Interval.QUARTER,
            price_type=PriceType.ALL_IN,
            local_tz=local_tz,
        )
        for day in days
    ]


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (ENERGY_SERVICE_NAME, {"price_type": "market_with_vat"}),
        (ENERGY_SERVICE_NAME, {"interval": "day"}),
        (GAS_SERVICE_NAME, {"price_type": "all_in"}),
        (GAS_SERVICE_NAME, {"interval": "quarter"}),
    ],
)
async def test_service_rejects_unsupported_options(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, str],
) -> None:
    """Only the electricity action accepts the supported new field values."""
    mock_energyzero.reset_mock()
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            service,
            {
                ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
                "incl_vat": True,
                **service_data,
            },
            blocking=True,
            return_response=True,
        )
    mock_energyzero.get_electricity_prices.assert_not_awaited()
    mock_energyzero.get_gas_prices.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("end", ["2026-04-10 00:15:00", "2026-04-10 00:10:00"])
async def test_energy_service_quarter_invalid_range(
    hass: HomeAssistant,
    mock_energyzero: AsyncMock,
    mock_config_entry: MockConfigEntry,
    end: str,
) -> None:
    """Reject empty or reversed quarter-hour ranges before calling the API."""
    mock_energyzero.reset_mock()
    with pytest.raises(ServiceValidationError, match="Invalid date range provided"):
        await hass.services.async_call(
            DOMAIN,
            ENERGY_SERVICE_NAME,
            {
                ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
                "incl_vat": True,
                "price_type": "all_in",
                "interval": "quarter",
                "start": "2026-04-10 00:15:00",
                "end": end,
            },
            blocking=True,
            return_response=True,
        )
    mock_energyzero.get_electricity_prices.assert_not_awaited()
