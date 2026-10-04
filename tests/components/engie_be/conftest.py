"""Common fixtures for the ENGIE Belgium tests."""

from collections.abc import Generator
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
    EngieBeEpexNotPublishedError,
    EpexGranularity,
    EpexPayload,
    EpexSlot,
    PricePeriod,
    PriceSlot,
    PricesResponse,
    ProductConfiguration,
    ServicePoint,
    bare_ean,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.engie_be.const import (
    CONF_MFA_METHOD,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.components.engie_be.coordinator import BRUSSELS_TIME_ZONE
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

EMAIL = "user@example.com"
PASSWORD = "hunter2"
SUBJECT = "auth0|69f5b418f3be21cc2ede9c98"
BAN = "000000000001"
BAN_2 = "000000000002"
OFFTAKE_ONLY_EAN = "541448820000000001_ID1"
OFFTAKE_INJECTION_EAN = "541448820000000002_ID1"
_SERVICE_POINT_ENERGY_TYPES = {
    bare_ean(OFFTAKE_ONLY_EAN): "GAS",
    bare_ean(OFFTAKE_INJECTION_EAN): "ELECTRICITY",
}


def _business_agreement(ban: str, *, with_address: bool = True) -> BusinessAgreement:
    """Build a single active business agreement."""
    return BusinessAgreement(
        business_agreement_number=ban,
        active=True,
        consumption_address=ConsumptionAddress(
            street="Main street",
            house_number="1",
            postal_code="1000",
            city="Brussels",
        )
        if with_address
        else None,
    )


def build_relations(*bans: str, with_address: bool = True) -> CustomerAccountRelations:
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
                        _business_agreement(ban, with_address=with_address)
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


def build_service_point(ean: str) -> ServicePoint:
    """Build a service point response for a queried (possibly suffixed) EAN."""
    bare = bare_ean(ean)
    return ServicePoint(ean_energy_types={bare: _SERVICE_POINT_ENERGY_TYPES[bare]})


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


def build_epex_payload_without_tomorrow(
    start: datetime,
    end: datetime,
    granularity: EpexGranularity = EpexGranularity.HOURLY,
) -> EpexPayload:
    """Raise for any window after today and build a payload otherwise."""
    if (
        start.astimezone(BRUSSELS_TIME_ZONE).date()
        > dt_util.now(BRUSSELS_TIME_ZONE).date()
    ):
        raise EngieBeEpexNotPublishedError("not published")
    return build_epex_payload(start, end, granularity)


def build_epex_payload_with_gap(
    start: datetime,
    end: datetime,
    granularity: EpexGranularity = EpexGranularity.HOURLY,
) -> EpexPayload:
    """Return an hourly payload without the slot covering the frozen afternoon."""
    payload = build_epex_payload(start, end, granularity)
    if granularity is not EpexGranularity.HOURLY:
        return payload
    gap_start = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    return EpexPayload(
        slots=tuple(slot for slot in payload.slots if slot.start != gap_start),
        slot_duration=payload.slot_duration,
    )


def build_epex_payload_with_stretched_slot(
    start: datetime,
    end: datetime,
    granularity: EpexGranularity = EpexGranularity.HOURLY,
) -> EpexPayload:
    """Return a payload where a skipped entry stretches the previous slot."""
    payload = build_epex_payload(start, end, granularity)
    stretched_start = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    slots = list(payload.slots)
    for index, slot in enumerate(slots[:-1]):
        if slot.start == stretched_start:
            slots[index] = EpexSlot(
                start=slot.start,
                end=slots[index + 1].end,
                value_eur_per_kwh=slot.value_eur_per_kwh,
            )
            del slots[index + 1]
            break
    return EpexPayload(slots=tuple(slots), slot_duration=payload.slot_duration)


def build_epex_payload_with_partial_tomorrow(
    start: datetime,
    end: datetime,
    granularity: EpexGranularity = EpexGranularity.HOURLY,
) -> EpexPayload:
    """Return one slot for tomorrow windows and a full payload otherwise."""
    if (
        start.astimezone(BRUSSELS_TIME_ZONE).date()
        > dt_util.now(BRUSSELS_TIME_ZONE).date()
    ):
        payload = build_epex_payload(start, end, granularity)
        return EpexPayload(slots=payload.slots[:1], slot_duration=payload.slot_duration)
    return build_epex_payload(start, end, granularity)


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
        "homeassistant.components.engie_be.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def frozen_afternoon(freezer: FrozenDateTimeFactory) -> None:
    """Freeze time on a Brussels Saturday afternoon."""
    freezer.move_to(datetime(2026, 10, 3, 14, 0, tzinfo=BRUSSELS_TIME_ZONE))


async def setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Set up a loaded ENGIE Belgium entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


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
