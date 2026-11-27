"""Common fixtures for the ENGIE Belgium tests."""

from collections.abc import Callable, Generator, Iterable
from datetime import UTC, date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from aioengiebelgium import (
    AccountRelation,
    AuthFlow,
    BusinessAgreement,
    ConsumptionAddress,
    CustomerAccount,
    CustomerAccountRelations,
    EanPrices,
    EnergyContract,
    EnergyContractsResponse,
    EngieBeCommunicationError,
    EpexGranularity,
    EpexPayload,
    EpexSlot,
    MonthlyPeaks,
    Peak,
    PricePeriod,
    PriceSlot,
    PricesResponse,
    ProductConfiguration,
    ServicePoint,
    ServicePointInstallation,
    ServicePointMarketDetails,
    bare_ean,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.engie_be.const import (
    BRUSSELS_TIME_ZONE,
    CONF_MFA_METHOD,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

EMAIL = "user@example.com"
PASSWORD = "hunter2"
SUBJECT = "auth0|69f5b418f3be21cc2ede9c98"
BAN = "000000000001"
BAN_2 = "000000000002"
OFFTAKE_ONLY_EAN = "541448820000000001_ID1"
EPEX_CURRENT_HOUR_UNIQUE_ID = f"{BAN}_epex_current_hour"
EPEX_TOMORROW_AVAILABLE_UNIQUE_ID = f"{BAN}_epex_tomorrow_available"
OFFTAKE_TOTAL_HOURS_UNIQUE_ID = f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
EPEX_LOW_TODAY_HOUR_UNIQUE_ID = f"{BAN}_epex_low_today_hour"
OFFTAKE_INJECTION_EAN = "541448820000000002_ID1"
GAS_CONVERSION_COEFFICIENT = 11.5
_SERVICE_POINT_ENERGY_TYPES = {
    bare_ean(OFFTAKE_ONLY_EAN): "GAS",
    bare_ean(OFFTAKE_INJECTION_EAN): "ELECTRICITY",
}


MAIN_STREET_ADDRESS = ConsumptionAddress(
    street="Main street", house_number="1", postal_code="1000", city="Brussels"
)


def build_relations(
    *bans: str, address: ConsumptionAddress | None = MAIN_STREET_ADDRESS
) -> CustomerAccountRelations:
    """Build a customer-account-relations response with the given active BANs."""
    bans = bans or (BAN,)
    return CustomerAccountRelations(
        accounts=(
            AccountRelation(
                id="account-1",
                admin=True,
                customer_account=CustomerAccount(
                    customer_account_number="can-1",
                    business_agreements=tuple(
                        BusinessAgreement(
                            business_agreement_number=ban,
                            active=True,
                            consumption_address=address,
                        )
                        for ban in bans
                    ),
                ),
            ),
        )
    )


def build_prices(
    *,
    valid_from: date | None = date(2000, 1, 1),
    valid_to: date | None = date(2099, 12, 31),
) -> PricesResponse:
    """Build a prices response with an offtake-only EAN and a dual-direction EAN."""
    return PricesResponse(
        items=(
            EanPrices(
                ean=OFFTAKE_ONLY_EAN,
                periods=(
                    PricePeriod(
                        valid_from=valid_from,
                        valid_to=valid_to,
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="TOTAL_HOURS",
                                price_value=0.123456,
                                price_value_excl_vat=0.116468,
                            ),
                        ),
                    ),
                ),
            ),
            EanPrices(
                ean=OFFTAKE_INJECTION_EAN,
                periods=(
                    PricePeriod(
                        valid_from=valid_from,
                        valid_to=valid_to,
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_OFFTAKE_PEAK",
                                price_value=0.18,
                                price_value_excl_vat=0.169811,
                            ),
                            PriceSlot(
                                time_of_use_slot_code="EN",
                                price_value=0.12,
                                price_value_excl_vat=0.113208,
                            ),
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_OFFTAKE_WEEKEND",
                                price_value=0.15,
                                price_value_excl_vat=0.141509,
                            ),
                        ),
                        injection=(
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_INJECTION_PEAK",
                                price_value=0.05,
                                price_value_excl_vat=0.047170,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def build_service_point(
    ean: str, *, gas_conversion_coefficient: float | None = GAS_CONVERSION_COEFFICIENT
) -> ServicePoint:
    """Build a service point response for a queried (possibly suffixed) EAN."""
    bare = bare_ean(ean)
    energy_type = _SERVICE_POINT_ENERGY_TYPES[bare]
    return ServicePoint(
        ean_energy_types={bare: energy_type},
        market_details=ServicePointMarketDetails(
            installation=ServicePointInstallation(
                gas_conversion_coefficient=gas_conversion_coefficient
                if energy_type == "GAS"
                else None
            )
        ),
    )


def build_contracts(*, dynamic: bool = False) -> EnergyContractsResponse:
    """Build an energy-contracts response with one active electricity contract."""
    return EnergyContractsResponse(
        items=(
            EnergyContract(
                business_agreement_number=BAN,
                service_point_number=bare_ean(OFFTAKE_INJECTION_EAN),
                division="ELECTRICITY",
                status="ACTIVE",
                product_configuration=ProductConfiguration(
                    energy_product="DYNAMIC" if dynamic else "FIXED"
                ),
            ),
        )
    )


def _api_timestamp(moment: datetime) -> datetime:
    """Return a timestamp carrying the fixed Brussels offset the API would send."""
    wall = BRUSSELS_TIME_ZONE.fromutc(moment.replace(tzinfo=BRUSSELS_TIME_ZONE))
    return wall.replace(tzinfo=timezone(wall.utcoffset()))


def build_epex_payload(
    start: datetime,
    end: datetime,
    granularity: EpexGranularity = EpexGranularity.HOURLY,
) -> EpexPayload:
    """Build an EPEX payload of Brussels-offset slots covering the window with rising values."""
    step = timedelta(minutes=granularity.value)
    slots: list[EpexSlot] = []
    moment = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    while moment < end_utc:
        local = moment.astimezone(BRUSSELS_TIME_ZONE)
        slots.append(
            EpexSlot(
                start=_api_timestamp(moment),
                end=_api_timestamp(moment + step),
                value_eur_per_kwh=round((local.hour + 1 + local.minute / 60) / 100, 6),
            )
        )
        moment = moment + step
    return EpexPayload(slots=tuple(slots), slot_duration=step)


def build_peak(start: datetime, *, power_kw: float = 4.2) -> Peak:
    """Build a 15-minute capacity tariff peak starting at the given moment."""
    return Peak(
        peak_kw=power_kw,
        peak_kwh=1.05,
        start=start,
        end=start + timedelta(minutes=15),
    )


def build_monthly_peaks(
    year: int,
    month: int,
    *,
    peak: Peak | None = None,
    daily_peaks: tuple[Peak, ...] = (),
) -> MonthlyPeaks:
    """Build a monthly peaks response for the given month."""
    return MonthlyPeaks(
        year=year,
        month=month,
        peak_of_the_month=peak,
        daily_peaks=daily_peaks,
    )


def build_monthly_peaks_for_request(ban: str, year: int, month: int) -> MonthlyPeaks:
    """Build a peaks response with one peak on the 15th of the requested month."""
    start = datetime(year, month, 15, 18, 0, tzinfo=BRUSSELS_TIME_ZONE)
    peak = build_peak(start)
    return build_monthly_peaks(year, month, peak=peak, daily_peaks=(peak,))


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        unique_id=SUBJECT,
        data={
            CONF_EMAIL: EMAIL,
            CONF_MFA_METHOD: "sms",
            CONF_ACCESS_TOKEN: "access-token",
            CONF_REFRESH_TOKEN: "refresh-token",
        },
    )


@pytest.fixture
def mock_engie_client(mock_auth_flow: MagicMock) -> Generator[MagicMock]:
    """Mock the EngieBeClient class constructed by the integration and config flow."""
    with (
        patch(
            "homeassistant.components.engie_be.EngieBeClient", autospec=True
        ) as mock_client_class,
        patch(
            "homeassistant.components.engie_be.config_flow.EngieBeClient",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.async_get_customer_account_relations.return_value = build_relations()
        client.async_get_prices.return_value = build_prices()
        client.async_get_service_point.side_effect = build_service_point
        client.async_get_energy_contracts.return_value = build_contracts()
        client.async_get_epex_prices.side_effect = build_epex_payload
        client.async_get_monthly_peaks.side_effect = build_monthly_peaks_for_request
        client.async_start_authentication.return_value = mock_auth_flow
        yield mock_client_class


@pytest.fixture
def mock_auth_flow() -> MagicMock:
    """Return a mock in-progress authentication flow."""
    auth_flow = MagicMock(spec=AuthFlow)
    auth_flow.async_submit_mfa = AsyncMock(
        return_value=("new-access-token", "new-refresh-token")
    )
    return auth_flow


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.engie_be.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def frozen_afternoon(freezer: FrozenDateTimeFactory) -> None:
    """Freeze time on a Brussels Saturday afternoon."""
    freezer.move_to(datetime(2026, 10, 3, 14, 0, tzinfo=BRUSSELS_TIME_ZONE))


def without_capacity_tariff(
    entries: Iterable[er.RegistryEntry],
) -> list[er.RegistryEntry]:
    """Return the given registry entries excluding the capacity tariff peak sensors."""
    return [entry for entry in entries if "_capacity_tariff_" not in entry.unique_id]


async def setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up a loaded ENGIE Belgium entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def advance_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move the clock forward and let the scheduled refreshes finish."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def contracts_failing_for(
    failing_ban: str, *, dynamic: bool = False
) -> Callable[[str], EnergyContractsResponse]:
    """Return a contracts side effect that fails for one household only."""

    def _contracts(ban: str) -> EnergyContractsResponse:
        if ban == failing_ban:
            raise EngieBeCommunicationError("boom")
        return build_contracts(dynamic=dynamic)

    return _contracts


def get_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: Platform,
    unique_id: str,
) -> State:
    """Return the state of an ENGIE Belgium entity and assert it exists."""
    state = hass.states.get(get_entity_id(entity_registry, platform, unique_id))
    assert state is not None
    return state


def get_entity_id(
    entity_registry: er.EntityRegistry, platform: Platform, unique_id: str
) -> str:
    """Return the entity ID of an ENGIE Belgium entity and assert it exists."""
    entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def setup_dynamic_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Set up an entry whose household has a dynamic electricity tariff."""
    mock_engie_client.return_value.async_get_energy_contracts.return_value = (
        build_contracts(dynamic=True)
    )
    await setup_entry(hass, mock_config_entry)
