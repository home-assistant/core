"""Test the ENGIE Belgium sensor platform."""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
import dataclasses
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from aioengiebelgium import (
    AccountRelation,
    BusinessAgreement,
    ConsumptionAddress,
    CustomerAccount,
    CustomerAccountRelations,
    EanPrices,
    EngieBeCommunicationError,
    EngieBeError,
    EpexGranularity,
    EpexPayload,
    PricePeriod,
    PriceSlot,
    PricesResponse,
    ServicePoint,
    bare_ean,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.engie_be import EngieBeHouseholdCoordinators
from homeassistant.components.engie_be.const import (
    CONTRACTS_RETRY_INTERVAL,
    DOMAIN,
    EPEX_SCAN_INTERVAL,
    HOUSEHOLD_SCAN_INTERVAL,
)
from homeassistant.components.engie_be.coordinator import (
    EngieBePricesCoordinator,
    EngieBePricesData,
    EngieBeTouCoordinator,
)
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    BAN,
    BAN_2,
    BRUSSELS_TIME_ZONE,
    ELECTRICITY_EAN_2,
    OFFTAKE_INJECTION_EAN,
    OFFTAKE_ONLY_EAN,
    build_contracts,
    build_epex_payload,
    build_epex_payload_with_gap,
    build_prices,
    build_relations,
    build_tou_schedules,
    setup_dynamic_entry,
    setup_entry,
    without_capacity_tariff,
)


@contextmanager
def _no_coordinator_refresh() -> Iterator[None]:
    """Freeze both coordinators so only boundary timers can update entities."""
    with (
        patch.object(
            EngieBeTouCoordinator, "_handle_refresh_interval", new=AsyncMock()
        ),
        patch.object(
            EngieBePricesCoordinator, "_handle_refresh_interval", new=AsyncMock()
        ),
    ):
        yield


def _prices_by_ban(
    mapping: Mapping[str, PricesResponse | EngieBeError],
) -> Callable[[str], PricesResponse]:
    """Return an async_get_prices side_effect that resolves independently per BAN."""

    def _side_effect(ban: str) -> PricesResponse:
        result = mapping[ban]
        if isinstance(result, EngieBeError):
            raise result
        return result

    return _side_effect


@pytest.mark.usefixtures("mock_engie_client", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the energy-price sensors for an offtake-only and a dual-direction EAN."""
    freezer.move_to(datetime(2026, 11, 15, 12, 0, tzinfo=BRUSSELS_TIME_ZONE))
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    for device_entry in sorted(device_entries, key=lambda entry: entry.id):
        assert device_entry == snapshot(name=f"{device_entry.name}-device")

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_engie_client")
async def test_slot_aware_naming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test known slot codes drive friendly names and unknown codes create no entity."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    total_hours_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
    )
    assert total_hours_entity_id is not None
    total_hours_state = hass.states.get(total_hours_entity_id)
    assert total_hours_state is not None
    assert "total_hours" not in total_hours_state.name.lower()

    peak_unique_id = f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_S_TOU1_OFFTAKE_PEAK"
    peak_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, peak_unique_id
    )
    assert peak_entity_id is not None
    peak_entry = entity_registry.async_get(peak_entity_id)
    assert peak_entry is not None
    assert peak_entry.unique_id == peak_unique_id
    peak_state = hass.states.get(peak_entity_id)
    assert peak_state is not None
    assert peak_state.name.endswith("Electricity peak offtake price")

    for slot_code in ("S_TOU1_OFFTAKE_WEEKEND", "EN"):
        assert (
            entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_{slot_code}"
            )
            is None
        )


@pytest.mark.usefixtures("mock_engie_client")
async def test_excl_vat_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test excl-VAT price sensors are disabled by default, incl-VAT ones are not."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = without_capacity_tariff(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    excl_vat_entries = [
        entry for entry in entity_entries if entry.unique_id.endswith("_excl_vat")
    ]
    incl_vat_entries = [
        entry for entry in entity_entries if not entry.unique_id.endswith("_excl_vat")
    ]

    assert excl_vat_entries
    assert incl_vat_entries
    assert all(
        entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for entry in excl_vat_entries
    )
    assert all(entry.disabled_by is None for entry in incl_vat_entries)


def _single_period_prices(ean: str) -> EanPrices:
    """Build a single-period, offtake-only EanPrices for the given EAN."""
    return EanPrices(
        ean=ean,
        periods=(
            PricePeriod(
                valid_from=date(2000, 1, 1),
                valid_to=date(2099, 12, 31),
                vat_tariff=6.0,
                offtake=(
                    PriceSlot(
                        time_of_use_slot_code="TOTAL_HOURS",
                        price_value=0.2,
                        price_value_excl_vat=0.19,
                    ),
                ),
            ),
        ),
    )


async def test_duplicate_type_suffix(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities get a distinct last-4 EAN suffix for two same-type household EANs."""
    eans = (OFFTAKE_INJECTION_EAN, ELECTRICITY_EAN_2)
    mock_engie_client.return_value.async_get_prices.return_value = PricesResponse(
        items=tuple(_single_period_prices(ean) for ean in eans)
    )
    mock_engie_client.return_value.async_get_service_point.side_effect = lambda ean: (
        ServicePoint(ean_energy_types={bare_ean(ean): "ELECTRICITY"})
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    names: dict[str, str] = {}
    for ean in eans:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_{ean}_offtake_TOTAL_HOURS"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        names[ean] = state.name

    for ean in eans:
        assert names[ean].endswith(f"({bare_ean(ean)[-4:]})")
    assert names[OFFTAKE_INJECTION_EAN] != names[ELECTRICITY_EAN_2]


async def test_type_fallback_when_service_point_lookup_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a failed service-point lookup falls back to the untyped entity name."""
    mock_engie_client.return_value.async_get_service_point.side_effect = [
        EngieBeCommunicationError("boom"),
        ServicePoint(ean_energy_types={bare_ean(OFFTAKE_INJECTION_EAN): "ELECTRICITY"}),
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name.endswith("Offtake price")


def _empty_address_relations() -> CustomerAccountRelations:
    """Build relations for a single BAN with an all-empty consumption address."""
    return CustomerAccountRelations(
        accounts=(
            AccountRelation(
                id="account-1",
                admin=True,
                customer_account=CustomerAccount(
                    customer_account_number="can-1",
                    business_agreements=(
                        BusinessAgreement(
                            business_agreement_number=BAN,
                            active=True,
                            consumption_address=ConsumptionAddress(
                                street="",
                                house_number="",
                                postal_code="",
                                city="",
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


@pytest.mark.parametrize(
    "relations",
    [
        pytest.param(build_relations(with_address=False), id="no-address"),
        pytest.param(_empty_address_relations(), id="empty-address"),
    ],
)
async def test_device_name_falls_back_to_ban(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    relations: CustomerAccountRelations,
) -> None:
    """Test the device name falls back to the bare BAN without a usable consumption address."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        relations
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    household_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BAN), mock_config_entry.entry_id
    )
    assert household_device is not None
    assert household_device.name == BAN


@pytest.mark.parametrize(
    ("valid_from", "valid_to"),
    [
        pytest.param(date(2026, 8, 1), date(2026, 9, 1), id="inside-window"),
        pytest.param(date(2026, 8, 13), date(2026, 9, 1), id="first-day-inclusive"),
        pytest.param(
            date(2026, 8, 1),
            date(2026, 9, 1),
            id="date-objects",
        ),
    ],
)
async def test_period_window_creates_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    valid_from: date | None,
    valid_to: date | None,
) -> None:
    """Test sensors are created with a numeric state for a period covering today."""
    freezer.move_to("2026-08-13T12:00:00+02:00")
    mock_engie_client.return_value.async_get_prices.return_value = build_prices(
        valid_from=valid_from, valid_to=valid_to
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = without_capacity_tariff(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    enabled_entries = [
        entity_entry
        for entity_entry in entity_entries
        if entity_entry.disabled_by is None
    ]
    assert enabled_entries
    for entity_entry in enabled_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        float(state.state)


async def test_period_window_uses_brussels_date(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test period selection uses the Brussels calendar date."""
    freezer.move_to("2026-08-12T22:30:00+00:00")
    mock_engie_client.return_value.async_get_prices.return_value = build_prices(
        valid_from=date(2026, 8, 13), valid_to=date(2026, 8, 14)
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert without_capacity_tariff(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )


@pytest.mark.parametrize(
    ("valid_from", "valid_to"),
    [
        pytest.param(date(2026, 8, 1), date(2026, 8, 13), id="last-day-exclusive"),
        pytest.param(date(2026, 1, 1), date(2026, 2, 1), id="expired-window"),
        pytest.param(None, date(2026, 9, 1), id="malformed-dates"),
    ],
)
async def test_period_window_skips_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    valid_from: date | None,
    valid_to: date | None,
) -> None:
    """Test no sensors are created when no period covers today (locks in exclusive valid_to)."""
    freezer.move_to("2026-08-13T12:00:00+02:00")
    mock_engie_client.return_value.async_get_prices.return_value = build_prices(
        valid_from=valid_from, valid_to=valid_to
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = without_capacity_tariff(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    assert without_capacity_tariff(entity_entries) == []


async def test_period_window_refresh_makes_existing_sensors_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test existing sensors become unavailable after the period expires."""
    freezer.move_to("2026-08-12T12:00:00+02:00")
    mock_engie_client.return_value.async_get_prices.return_value = build_prices(
        valid_from=date(2026, 8, 1), valid_to=date(2026, 8, 13)
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = without_capacity_tariff(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    enabled_entity_entries = [
        entity_entry
        for entity_entry in entity_entries
        if entity_entry.disabled_by is None
    ]
    assert enabled_entity_entries

    freezer.tick(timedelta(days=1, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for entity_entry in enabled_entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id) is not None
        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


def _degraded_slots_empty() -> EngieBePricesData:
    """Return prices data with no slots or EANs at all."""
    return EngieBePricesData(slots={}, eans=(), prices_by_ean={})


def _degraded_period_expired() -> EngieBePricesData:
    """Return prices data whose only period for the EAN has expired."""
    return EngieBePricesData(slots={}, eans=(OFFTAKE_ONLY_EAN,), prices_by_ean={})


def _degraded_slot_code_absent() -> EngieBePricesData:
    """Return prices data whose current period has no matching offtake slot."""
    return EngieBePricesData(
        slots={
            (OFFTAKE_ONLY_EAN, "offtake", "OTHER_CODE"): PriceSlot(
                time_of_use_slot_code="OTHER_CODE",
                price_value=0.5,
                price_value_excl_vat=0.5,
            )
        },
        eans=(OFFTAKE_ONLY_EAN,),
        prices_by_ean={},
    )


def _degraded_ean_absent() -> EngieBePricesData:
    """Return prices data whose slots belong to a different EAN entirely."""
    return EngieBePricesData(
        slots={
            (OFFTAKE_INJECTION_EAN, "offtake", "TOTAL_HOURS"): PriceSlot(
                time_of_use_slot_code="TOTAL_HOURS",
                price_value=0.5,
                price_value_excl_vat=0.5,
            )
        },
        eans=(OFFTAKE_INJECTION_EAN,),
        prices_by_ean={},
    )


@pytest.mark.usefixtures("mock_engie_client")
@pytest.mark.parametrize(
    "degraded_data",
    [
        pytest.param(_degraded_slots_empty, id="slots-empty"),
        pytest.param(_degraded_period_expired, id="period-expired"),
        pytest.param(_degraded_slot_code_absent, id="slot-code-absent"),
        pytest.param(_degraded_ean_absent, id="ean-absent"),
    ],
)
async def test_available_degrades_for_missing_slot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    degraded_data: Callable[[], EngieBePricesData],
) -> None:
    """Test a missing slot key makes the entity unavailable for every degraded-data branch."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
    )
    assert entity_id is not None

    coordinator = mock_config_entry.runtime_data.households[BAN].prices
    coordinator.async_set_updated_data(degraded_data())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_recovering_ban_adds_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a BAN that fails on the first refresh gets its sensors once it recovers."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )
    mock_engie_client.return_value.async_get_prices.side_effect = [
        build_prices(),
        EngieBeCommunicationError("boom"),
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ban_2_unique_id = f"{BAN_2}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
    assert (
        entity_registry.async_get_entity_id("sensor", DOMAIN, ban_2_unique_id) is None
    )

    mock_engie_client.return_value.async_get_prices.side_effect = [
        build_prices(),
        build_prices(),
    ]
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    ban_2_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, ban_2_unique_id
    )
    assert ban_2_entity_id is not None
    entity_entry = entity_registry.async_get(ban_2_entity_id)
    assert entity_entry is not None
    ban_2_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BAN_2), mock_config_entry.entry_id
    )
    assert ban_2_device is not None
    assert entity_entry.device_id == ban_2_device.id


async def test_period_gap_heals(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors appear once today enters a price period that was a gap at setup."""
    freezer.move_to("2026-08-13T12:00:00+02:00")
    mock_engie_client.return_value.async_get_prices.return_value = build_prices(
        valid_from=date(2026, 8, 14), valid_to=date(2026, 9, 1)
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        without_capacity_tariff(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == []
    )

    freezer.tick(timedelta(days=1, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert without_capacity_tariff(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )


def _add_offtake_slot(
    prices: PricesResponse, ean: str, slot: PriceSlot
) -> PricesResponse:
    """Return a copy of prices with an extra offtake slot added to one EAN's periods."""
    return PricesResponse(
        items=tuple(
            dataclasses.replace(
                ean_prices,
                periods=tuple(
                    dataclasses.replace(period, offtake=(*period.offtake, slot))
                    for period in ean_prices.periods
                ),
            )
            if ean_prices.ean == ean
            else ean_prices
            for ean_prices in prices.items
        )
    )


def _reprice_offtake_slot(
    prices: PricesResponse, ean: str, slot_code: str, incl_vat: float, excl_vat: float
) -> PricesResponse:
    """Return a copy of prices with one offtake slot's price values changed."""
    return PricesResponse(
        items=tuple(
            dataclasses.replace(
                ean_prices,
                periods=tuple(
                    dataclasses.replace(
                        period,
                        offtake=tuple(
                            dataclasses.replace(
                                slot,
                                price_value=incl_vat,
                                price_value_excl_vat=excl_vat,
                            )
                            if slot.time_of_use_slot_code == slot_code
                            else slot
                            for slot in period.offtake
                        ),
                    )
                    for period in ean_prices.periods
                ),
            )
            if ean_prices.ean == ean
            else ean_prices
            for ean_prices in prices.items
        )
    )


async def test_new_slot_code_appears(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new time-of-use slot code adds exactly its incl/excl VAT sensor pair."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    count_before = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    extra_slot = PriceSlot(
        time_of_use_slot_code="S_TOU1_OFFTAKE_OFFPEAK",
        price_value=0.09,
        price_value_excl_vat=0.084906,
    )
    mock_engie_client.return_value.async_get_prices.return_value = _add_offtake_slot(
        build_prices(), OFFTAKE_INJECTION_EAN, extra_slot
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    count_after = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    assert count_after == count_before + 2

    incl_vat_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_S_TOU1_OFFTAKE_OFFPEAK",
    )
    excl_vat_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_S_TOU1_OFFTAKE_OFFPEAK_excl_vat",
    )
    assert incl_vat_id is not None
    assert excl_vat_id is not None


@pytest.mark.usefixtures("frozen_afternoon")
async def test_update_entity_refreshes_prices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Update entity action fetches new prices for the active price sensor."""
    assert await async_setup_component(hass, "homeassistant", {})
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert active_price_id is not None
    active_price = hass.states.get(active_price_id)
    assert active_price is not None
    assert float(active_price.state) == pytest.approx(0.18)

    client.async_get_prices.return_value = _reprice_offtake_slot(
        build_prices(),
        OFFTAKE_INJECTION_EAN,
        "S_TOU1_OFFTAKE_PEAK",
        0.25,
        0.235849,
    )
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": active_price_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    active_price = hass.states.get(active_price_id)
    assert active_price is not None
    assert float(active_price.state) == pytest.approx(0.25)


async def test_no_duplicate_entities_on_repeated_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test refreshing with identical data does not add duplicate entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    count_before = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )

    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    count_after = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    assert count_after == count_before


async def test_late_service_point_failure_falls_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a recovering BAN whose new EAN fails its service-point lookup falls back."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )
    ban_2_prices = PricesResponse(items=(_single_period_prices(ELECTRICITY_EAN_2),))
    mock_engie_client.return_value.async_get_prices.side_effect = [
        build_prices(),
        EngieBeCommunicationError("boom"),
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {BAN: build_prices(), BAN_2: ban_2_prices}
    )
    mock_engie_client.return_value.async_get_service_point.side_effect = (
        EngieBeCommunicationError("boom")
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN_2}_{ELECTRICITY_EAN_2}_offtake_TOTAL_HOURS"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name.endswith("Offtake price")


def _prices_entity_id(entity_registry: er.EntityRegistry, ban: str) -> str:
    """Return the entity_id for a BAN's offtake-only price sensor."""
    unique_id = f"{ban}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


def _single_ban_prices_response(ean: str, price_value: float) -> PricesResponse:
    """Build a prices response with one offtake slot for the given EAN and price."""
    return PricesResponse(
        items=(
            EanPrices(
                ean=ean,
                periods=(
                    PricePeriod(
                        valid_from=date(2000, 1, 1),
                        valid_to=date(2099, 12, 31),
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="TOTAL_HOURS",
                                price_value=price_value,
                                price_value_excl_vat=price_value,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


async def _setup_two_bans(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Set up a config entry with two business agreements and initial prices."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )
    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {
            BAN: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.1),
            BAN_2: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.2),
        }
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_single_ban_transient_failure_goes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a transient failure for one BAN makes only that BAN's sensor unavailable."""
    await _setup_two_bans(hass, mock_config_entry, mock_engie_client)

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {
            BAN: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.3),
            BAN_2: EngieBeCommunicationError("boom"),
        }
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state_ban = hass.states.get(_prices_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_prices_entity_id(entity_registry, BAN_2))
    assert state_ban is not None
    assert state_ban_2 is not None
    assert state_ban.state == "0.3"
    assert state_ban_2.state == STATE_UNAVAILABLE


async def test_all_bans_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all BANs failing on refresh makes every sensor unavailable."""
    await _setup_two_bans(hass, mock_config_entry, mock_engie_client)

    mock_engie_client.return_value.async_get_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state_ban = hass.states.get(_prices_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_prices_entity_id(entity_registry, BAN_2))
    assert state_ban is not None
    assert state_ban_2 is not None
    assert state_ban.state == STATE_UNAVAILABLE
    assert state_ban_2.state == STATE_UNAVAILABLE
    assert not hass.config_entries.flow.async_progress()


async def test_unexpected_exception_is_not_swallowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected non-EngieBeError exception is logged instead of being swallowed."""
    await _setup_two_bans(hass, mock_config_entry, mock_engie_client)

    mock_engie_client.return_value.async_get_prices.side_effect = ValueError("boom")
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Unexpected error fetching" in caplog.text


async def test_failure_and_recovery_are_logged_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing BAN logs one error, stays quiet on repeat failures, then logs one recovery."""
    await _setup_two_bans(hass, mock_config_entry, mock_engie_client)
    caplog.set_level("DEBUG", logger="homeassistant.components.engie_be")

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {
            BAN: EngieBeCommunicationError("boom"),
            BAN_2: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.2),
        }
    )
    caplog.clear()
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count("Error fetching") == 1
    assert "recovered" not in caplog.text
    caplog.clear()

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {
            BAN: EngieBeCommunicationError("boom"),
            BAN_2: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.3),
        }
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error fetching" not in caplog.text
    caplog.clear()

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {
            BAN: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.4),
            BAN_2: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.5),
        }
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count("recovered") == 1

    state_ban = hass.states.get(_prices_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_prices_entity_id(entity_registry, BAN_2))
    assert state_ban is not None
    assert state_ban_2 is not None
    assert state_ban.state == "0.4"
    assert state_ban_2.state == "0.5"


async def test_recovery_after_all_bans_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors recover with fresh values after all BANs previously failed."""
    await _setup_two_bans(hass, mock_config_entry, mock_engie_client)

    mock_engie_client.return_value.async_get_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {
            BAN: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.4),
            BAN_2: _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.5),
        }
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state_ban = hass.states.get(_prices_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_prices_entity_id(entity_registry, BAN_2))
    assert state_ban is not None
    assert state_ban_2 is not None
    assert state_ban.state == "0.4"
    assert state_ban_2.state == "0.5"


async def test_service_point_transient_failure_is_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed service-point fetch is retried on the next refresh cycle."""
    caplog.set_level("DEBUG", logger="homeassistant.components.engie_be")
    mock_engie_client.return_value.async_get_prices.return_value = (
        _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.1)
    )
    mock_engie_client.return_value.async_get_service_point.side_effect = [
        EngieBeCommunicationError("boom"),
        ServicePoint(ean_energy_types={bare_ean(OFFTAKE_ONLY_EAN): "GAS"}),
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "Fetching service point for …0001 failed" in caplog.text
    assert "…_ID1" not in caplog.text

    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_engie_client.return_value.async_get_service_point.call_count == 2


async def test_service_point_success_without_ean_is_cached_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a successful fetch omitting the EAN is cached once and not retried."""
    mock_engie_client.return_value.async_get_prices.return_value = (
        _single_ban_prices_response(OFFTAKE_ONLY_EAN, 0.1)
    )
    mock_engie_client.return_value.async_get_service_point.side_effect = lambda ean: (
        ServicePoint(ean_energy_types={})
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(HOUSEHOLD_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_engie_client.return_value.async_get_service_point.call_count == 1


@pytest.mark.usefixtures("frozen_afternoon")
async def test_epex_entities_on_household_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the EPEX entities belong to the device of their household."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    household_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BAN), mock_config_entry.entry_id
    )
    assert household_device is not None
    epex_entries = [
        entity_entry
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entity_entry.unique_id.startswith(f"{BAN}_epex_")
    ]
    assert len(epex_entries) == 9
    assert {entity_entry.device_id for entity_entry in epex_entries} == {
        household_device.id
    }


@pytest.mark.usefixtures("frozen_afternoon")
async def test_epex_sensors_unknown_during_slot_gap(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the hourly current price reads unknown while its slot is missing."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_with_gap
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    hourly_current = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_current_hour"
    )
    assert hourly_current is not None
    hourly_current_state = hass.states.get(hourly_current)
    assert hourly_current_state is not None
    assert hourly_current_state.state == STATE_UNKNOWN

    quarter_current = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_current_quarter_hour"
    )
    assert quarter_current is not None
    quarter_current_state = hass.states.get(quarter_current)
    assert quarter_current_state is not None
    assert float(quarter_current_state.state) == pytest.approx(0.15)

    next_hour = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_next_hour"
    )
    assert next_hour is not None
    next_hour_state = hass.states.get(next_hour)
    assert next_hour_state is not None
    assert float(next_hour_state.state) == pytest.approx(0.16)

    hourly_low = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_low_today_hour"
    )
    assert hourly_low is not None
    hourly_low_state = hass.states.get(hourly_low)
    assert hourly_low_state is not None
    assert hourly_low_state.state == STATE_UNKNOWN

    hourly_high = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_high_today_hour"
    )
    assert hourly_high is not None
    hourly_high_state = hass.states.get(hourly_high)
    assert hourly_high_state is not None
    assert hourly_high_state.state == STATE_UNKNOWN

    quarter_low = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_low_today_quarter_hour"
    )
    assert quarter_low is not None
    quarter_low_state = hass.states.get(quarter_low)
    assert quarter_low_state is not None
    assert float(quarter_low_state.state) == pytest.approx(0.01)


async def test_epex_sensors_update_on_quarter_boundaries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entity states refresh on quarter boundaries without an API call."""
    freezer.move_to(datetime(2026, 10, 3, 14, 7, tzinfo=BRUSSELS_TIME_ZONE))
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    quarter_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_current_quarter_hour"
    )
    assert quarter_entity_id is not None
    before_state = hass.states.get(quarter_entity_id)
    assert before_state is not None
    assert float(before_state.state) == pytest.approx(0.15)

    call_count = mock_engie_client.return_value.async_get_epex_prices.call_count
    freezer.move_to(datetime(2026, 10, 3, 14, 15, tzinfo=BRUSSELS_TIME_ZONE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    after_state = hass.states.get(quarter_entity_id)
    assert after_state is not None
    assert float(after_state.state) == pytest.approx(0.1525)
    assert mock_engie_client.return_value.async_get_epex_prices.call_count == (
        call_count
    )


def _epex_state(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, key: str
) -> str:
    """Return the state of one EPEX entity of the dynamic household."""
    platform = "binary_sensor" if key == "epex_tomorrow_available" else "sensor"
    entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, f"{BAN}_{key}")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        pytest.param(
            datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
            {"epex_current_hour": 0.03, "epex_next_hour": 0.03},
            id="fall_back_repeated_hour",
        ),
        pytest.param(
            datetime(2026, 3, 29, 0, 30, tzinfo=UTC),
            {"epex_current_hour": 0.02, "epex_next_hour": 0.04},
            id="spring_forward_skipped_hour",
        ),
    ],
)
async def test_epex_sensors_on_dst_days(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    moment: datetime,
    expected: dict[str, float],
) -> None:
    """Test the EPEX sensors cover the 23 and 25 hour days."""
    freezer.move_to(moment)
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    expected |= {
        "epex_low_today_hour": 0.01,
        "epex_high_today_hour": 0.24,
        "epex_low_today_quarter_hour": 0.01,
        "epex_high_today_quarter_hour": 0.2475,
    }
    for key, value in expected.items():
        assert float(_epex_state(hass, entity_registry, key)) == pytest.approx(value)
    assert _epex_state(hass, entity_registry, "epex_tomorrow_available") == STATE_ON


@pytest.mark.usefixtures("frozen_afternoon")
async def test_epex_empty_payload_keeps_entities_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an empty payload leaves the entities unknown and is fetched again."""

    def _empty_payload(
        start: datetime,
        end: datetime,
        granularity: EpexGranularity = EpexGranularity.HOURLY,
    ) -> EpexPayload:
        """Return an EPEX payload without slots."""
        payload = build_epex_payload(start, end, granularity)
        return EpexPayload(slots=(), slot_duration=payload.slot_duration)

    client = mock_engie_client.return_value
    client.async_get_epex_prices.side_effect = _empty_payload
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    assert _epex_state(hass, entity_registry, "epex_current_hour") == STATE_UNKNOWN
    assert _epex_state(hass, entity_registry, "epex_low_today_hour") == STATE_UNKNOWN
    assert _epex_state(hass, entity_registry, "epex_tomorrow_available") == STATE_OFF

    call_count = client.async_get_epex_prices.call_count
    freezer.tick(EPEX_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_get_epex_prices.call_count == call_count + 4


@pytest.mark.usefixtures("frozen_afternoon")
async def test_epex_slot_gap_heals_on_next_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a day with a missing slot is fetched again and fills the daily sensors."""
    client = mock_engie_client.return_value
    client.async_get_epex_prices.side_effect = build_epex_payload_with_gap
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    assert _epex_state(hass, entity_registry, "epex_low_today_hour") == STATE_UNKNOWN

    call_count = client.async_get_epex_prices.call_count
    client.async_get_epex_prices.side_effect = build_epex_payload
    freezer.tick(EPEX_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_get_epex_prices.call_count == call_count + 1
    assert float(
        _epex_state(hass, entity_registry, "epex_current_hour")
    ) == pytest.approx(0.16)
    assert float(
        _epex_state(hass, entity_registry, "epex_low_today_hour")
    ) == pytest.approx(0.01)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "frozen_afternoon")
async def test_epex_sensors_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensors of a household with a dynamic tariff."""
    with patch("homeassistant.components.engie_be._PLATFORMS", [Platform.SENSOR]):
        await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


def _tou_entity_id(entity_registry: er.EntityRegistry, unique_id: str) -> str | None:
    """Return the entity id of a time-of-use entity."""
    return entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tou_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the slot sensors and the active price sensor of a TOU household."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    supplier_offtake_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot"
    )
    assert supplier_offtake_id is not None
    supplier_offtake = hass.states.get(supplier_offtake_id)
    assert supplier_offtake is not None
    assert supplier_offtake.state == "peak"
    assert supplier_offtake.attributes["options"] == ["exclusive_night", "peak"]
    assert supplier_offtake.attributes["optimal_slot"] == "exclusive_night"
    assert supplier_offtake.attributes["next_transition"] == datetime(
        2026, 10, 3, 22, 0, tzinfo=BRUSSELS_TIME_ZONE
    )
    weekday_slots = supplier_offtake.attributes["weekday_slots"]
    assert [slot["code"] for slot in weekday_slots["saturday"]] == [
        "peak",
        "exclusive_night",
    ]

    supplier_injection_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_tou_slot"
    )
    assert supplier_injection_id is not None
    supplier_injection = hass.states.get(supplier_injection_id)
    assert supplier_injection is not None
    assert supplier_injection.state == "peak"

    grid_offtake_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_grid_slot"
    )
    assert grid_offtake_id is not None
    grid_offtake = hass.states.get(grid_offtake_id)
    assert grid_offtake is not None
    assert grid_offtake.state == "peak"
    assert grid_offtake.attributes["optimal_slot"] == "offpeak"

    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_grid_slot"
        )
        is None
    )

    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert active_price_id is not None
    active_price = hass.states.get(active_price_id)
    assert active_price is not None
    assert float(active_price.state) == pytest.approx(0.18)
    assert active_price.attributes["slot_code"] == "peak"
    assert active_price.attributes["next_transition"] == datetime(
        2026, 10, 3, 22, 0, tzinfo=BRUSSELS_TIME_ZONE
    )
    assert active_price.attributes["next_slot_code"] == "exclusive_night"
    assert float(active_price.attributes["next_price"]) == pytest.approx(0.12)

    injection_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price"
    )
    assert injection_price_id is not None
    injection_price = hass.states.get(injection_price_id)
    assert injection_price is not None
    assert float(injection_price.state) == pytest.approx(0.05)
    assert injection_price.attributes["slot_code"] == "peak"
    assert injection_price.attributes["next_slot_code"] == "offpeak"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "frozen_afternoon")
async def test_tou_sensors_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the entity names of a household on a time-of-use tariff."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tou_boundary_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the TOU sensors flip on the slot boundary without a coordinator refresh."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    with _no_coordinator_refresh():
        freezer.tick(timedelta(hours=8, minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert client.async_get_tou_schedules.call_count == 1

    supplier_offtake_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot"
    )
    assert hass.states.get(supplier_offtake_id).state == "exclusive_night"

    supplier_injection_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_tou_slot"
    )
    assert hass.states.get(supplier_injection_id).state == "offpeak"

    grid_offtake_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_grid_slot"
    )
    assert hass.states.get(grid_offtake_id).state == "offpeak"

    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    active_price = hass.states.get(active_price_id)
    assert float(active_price.state) == pytest.approx(0.12)
    assert active_price.attributes["slot_code"] == "exclusive_night"
    assert active_price.attributes["next_slot_code"] == "peak"
    assert float(active_price.attributes["next_price"]) == pytest.approx(0.18)

    injection_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price"
    )
    injection_price = hass.states.get(injection_price_id)
    assert injection_price.state == STATE_UNKNOWN
    assert injection_price.attributes["slot_code"] == "offpeak"


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tou_single_rate_schedules_create_no_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test flat schedules create no time-of-use entities."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules(
        supplier_tou=False,
        network_tou=False,
    )
    await setup_entry(hass, mock_config_entry)

    for unique_id in (
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot",
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_tou_slot",
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_grid_slot",
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_grid_slot",
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price",
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price",
    ):
        assert _tou_entity_id(entity_registry, unique_id) is None


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tou_dynamic_household_has_no_active_price(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a dynamic household keeps slot sensors but gets no active price."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot"
        )
        is not None
    )
    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
        )
        is None
    )
    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price"
        )
        is None
    )


def _peak_only_prices_response() -> PricesResponse:
    """Build prices with one EAN and a single peak-only offtake slot."""
    return PricesResponse(
        items=(
            EanPrices(
                ean=OFFTAKE_INJECTION_EAN,
                periods=(
                    PricePeriod(
                        valid_from=date(2000, 1, 1),
                        valid_to=date(2099, 12, 31),
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_OFFTAKE_PEAK",
                                price_value=0.18,
                                price_value_excl_vat=0.169811,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


@pytest.mark.usefixtures("frozen_afternoon")
async def test_injection_current_price_absent_without_injection_prices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a switching injection schedule without injection prices gets no entity."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    client.async_get_prices.return_value = _peak_only_prices_response()
    await setup_entry(hass, mock_config_entry)

    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
        )
        is not None
    )
    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price"
        )
        is None
    )


@pytest.mark.usefixtures("frozen_afternoon")
async def test_high_load_hours_slot_names_as_peak(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the HIGH_LOAD_HOURS alias resolves to the peak entity name."""
    client = mock_engie_client.return_value
    client.async_get_prices.return_value = PricesResponse(
        items=(
            EanPrices(
                ean=OFFTAKE_INJECTION_EAN,
                periods=(
                    PricePeriod(
                        valid_from=date(2000, 1, 1),
                        valid_to=date(2099, 12, 31),
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="HIGH_LOAD_HOURS",
                                price_value=0.2,
                                price_value_excl_vat=0.188679,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    await setup_entry(hass, mock_config_entry)

    entity_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_HIGH_LOAD_HOURS"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert "peak" in state.name.lower()


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tou_schedules_failure_degrades_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test TOU entities go unavailable when the schedules fetch starts failing."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    supplier_offtake_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot"
    )
    assert hass.states.get(supplier_offtake_id).state == "peak"
    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert hass.states.get(active_price_id).state != STATE_UNAVAILABLE

    client.async_get_tou_schedules.side_effect = EngieBeCommunicationError("boom")
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(supplier_offtake_id).state == STATE_UNAVAILABLE
    assert hass.states.get(active_price_id).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tou_entities_created_despite_prices_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test slot sensors exist even when the prices fetch fails."""
    client = mock_engie_client.return_value
    client.async_get_prices.side_effect = EngieBeCommunicationError("boom")
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    supplier_offtake_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot"
    )
    assert supplier_offtake_id is not None
    assert hass.states.get(supplier_offtake_id).state == "peak"
    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
        )
        is None
    )


@pytest.mark.usefixtures("frozen_afternoon")
async def test_active_price_absent_while_tariff_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no active price entity exists while the tariff classification is pending."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot"
        )
        is not None
    )
    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
        )
        is None
    )


@pytest.mark.usefixtures("frozen_afternoon")
async def test_active_price_appears_when_retry_resolves_fixed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a classification retry that resolves to fixed adds the active price."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)
    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
        )
        is None
    )

    freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (
        _tou_entity_id(
            entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
        )
        is None
    )

    client.async_get_energy_contracts.side_effect = lambda _ban: build_contracts()
    freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert active_price_id is not None
    active_price = hass.states.get(active_price_id)
    assert active_price is not None
    assert float(active_price.state) == pytest.approx(0.18)
    injection_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price"
    )
    assert injection_price_id is not None
    injection_price = hass.states.get(injection_price_id)
    assert injection_price is not None
    assert float(injection_price.state) == pytest.approx(0.05)


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tou_entities_with_ean_suffix_for_duplicate_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test duplicate electricity meters get the EAN suffix in the entity names."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules(
        with_second_meter=True
    )
    client.async_get_prices.return_value = PricesResponse(
        items=tuple(
            EanPrices(
                ean=ean,
                periods=(
                    PricePeriod(
                        valid_from=date(2000, 1, 1),
                        valid_to=date(2099, 12, 31),
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="TOTAL_HOURS",
                                price_value=0.123456,
                                price_value_excl_vat=0.116468,
                            ),
                        ),
                        injection=(
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_INJECTION_PEAK",
                                price_value=0.05,
                                price_value_excl_vat=0.04717,
                            ),
                        ),
                    ),
                ),
            )
            for ean in (OFFTAKE_INJECTION_EAN, ELECTRICITY_EAN_2)
        )
    )
    await setup_entry(hass, mock_config_entry)

    for unique_id, suffix in (
        (f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_tou_slot", "0002"),
        (f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_tou_slot", "0002"),
        (f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_grid_slot", "0002"),
        (f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price", "0002"),
        (f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price", "0002"),
        (f"{BAN}_{ELECTRICITY_EAN_2}_offtake_tou_slot", "0003"),
        (f"{BAN}_{ELECTRICITY_EAN_2}_injection_tou_slot", "0003"),
        (f"{BAN}_{ELECTRICITY_EAN_2}_offtake_grid_slot", "0003"),
        (f"{BAN}_{ELECTRICITY_EAN_2}_offtake_current_price", "0003"),
        (f"{BAN}_{ELECTRICITY_EAN_2}_injection_current_price", "0003"),
    ):
        entity_id = _tou_entity_id(entity_registry, unique_id)
        assert entity_id is not None
        assert suffix in hass.states.get(entity_id).name


@pytest.mark.usefixtures("frozen_afternoon")
async def test_active_price_boundary_survives_unmatched_slot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the boundary timer keeps firing while no price slot matches the schedule."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    client.async_get_prices.return_value = _peak_only_prices_response()
    await setup_entry(hass, mock_config_entry)

    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert float(hass.states.get(active_price_id).state) == pytest.approx(0.18)

    with _no_coordinator_refresh():
        freezer.tick(timedelta(hours=8, minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get(active_price_id).state == STATE_UNKNOWN

        freezer.tick(timedelta(hours=8, minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert float(hass.states.get(active_price_id).state) == pytest.approx(0.18)


@pytest.mark.usefixtures("frozen_afternoon")
async def test_active_price_created_with_bare_ean_prices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the active price sensor is created when prices are keyed by bare EAN."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    client.async_get_prices.return_value = PricesResponse(
        items=tuple(
            dataclasses.replace(item, ean=bare_ean(item.ean))
            for item in build_prices().items
        )
    )
    await setup_entry(hass, mock_config_entry)

    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert active_price_id is not None
    assert float(hass.states.get(active_price_id).state) == pytest.approx(0.18)
    assert "0002" not in hass.states.get(active_price_id).name


@pytest.mark.usefixtures("frozen_afternoon")
@pytest.mark.parametrize(
    "degrade",
    [
        pytest.param(
            lambda household: household.tou.async_set_updated_data({}),
            id="schedule_ean_absent",
        ),
        pytest.param(
            lambda household: household.prices.async_set_updated_data(
                EngieBePricesData(slots={}, eans=(), prices_by_ean={})
            ),
            id="prices_ean_absent",
        ),
    ],
)
async def test_active_price_unavailable_when_meter_dropped_from_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    degrade: Callable[[EngieBeHouseholdCoordinators], None],
) -> None:
    """Test the active price entity goes unavailable when a refresh drops its meter."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert hass.states.get(active_price_id).state != STATE_UNAVAILABLE

    degrade(mock_config_entry.runtime_data.households[BAN])
    await hass.async_block_till_done()

    assert hass.states.get(active_price_id).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("frozen_afternoon")
async def test_injection_price_unavailable_when_injection_prices_drop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the injection price goes unavailable when its price slots disappear."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    injection_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price"
    )
    offtake_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert hass.states.get(injection_price_id).state != STATE_UNAVAILABLE

    household = mock_config_entry.runtime_data.households[BAN]
    household.prices.async_set_updated_data(
        EngieBePricesData(
            slots={},
            eans=(OFFTAKE_INJECTION_EAN,),
            prices_by_ean={
                OFFTAKE_INJECTION_EAN: _peak_only_prices_response().items[0]
            },
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get(injection_price_id).state == STATE_UNAVAILABLE
    assert hass.states.get(offtake_price_id).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("frozen_afternoon")
async def test_injection_price_unavailable_when_injection_schedule_drops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the injection price goes unavailable when its direction schedule disappears."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    await setup_entry(hass, mock_config_entry)

    injection_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_injection_current_price"
    )
    offtake_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    assert float(hass.states.get(injection_price_id).state) == pytest.approx(0.05)

    client.async_get_tou_schedules.return_value = build_tou_schedules(
        with_supplier_injection=False
    )
    freezer.tick(HOUSEHOLD_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(injection_price_id).state == STATE_UNAVAILABLE
    assert float(hass.states.get(offtake_price_id).state) == pytest.approx(0.18)


def _two_period_prices(
    first_valid_to: date,
    second_valid_from: date,
    first_night_price: float | None,
) -> PricesResponse:
    """Build prices with two periods around the frozen Saturday."""
    first_offtake = [
        PriceSlot(
            time_of_use_slot_code="S_TOU1_OFFTAKE_PEAK",
            price_value=0.18,
            price_value_excl_vat=0.169811,
        )
    ]
    if first_night_price is not None:
        first_offtake.append(
            PriceSlot(
                time_of_use_slot_code="EN",
                price_value=first_night_price,
                price_value_excl_vat=first_night_price,
            )
        )
    return PricesResponse(
        items=(
            EanPrices(
                ean=OFFTAKE_INJECTION_EAN,
                periods=(
                    PricePeriod(
                        valid_from=date(2000, 1, 1),
                        valid_to=first_valid_to,
                        vat_tariff=6.0,
                        offtake=tuple(first_offtake),
                    ),
                    PricePeriod(
                        valid_from=second_valid_from,
                        valid_to=date(2099, 12, 31),
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_OFFTAKE_PEAK",
                                price_value=0.20,
                                price_value_excl_vat=0.188679,
                            ),
                            PriceSlot(
                                time_of_use_slot_code="EN",
                                price_value=0.13,
                                price_value_excl_vat=0.122642,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


@pytest.mark.usefixtures("frozen_afternoon")
@pytest.mark.parametrize(
    (
        "first_valid_to",
        "second_valid_from",
        "first_night_price",
        "initial_state",
        "night_state",
    ),
    [
        pytest.param(
            date(2026, 10, 4),
            date(2026, 10, 4),
            0.12,
            "0.18",
            "0.12",
            id="priced_night_rollover",
        ),
        pytest.param(
            date(2026, 10, 4),
            date(2026, 10, 4),
            None,
            "0.18",
            STATE_UNKNOWN,
            id="missing_night_price",
        ),
        pytest.param(
            date(2026, 10, 3),
            date(2026, 10, 4),
            0.12,
            STATE_UNKNOWN,
            STATE_UNKNOWN,
            id="gap_before_next_period",
        ),
    ],
)
async def test_active_price_wakes_at_period_boundary_without_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    first_valid_to: date,
    second_valid_from: date,
    first_night_price: float | None,
    initial_state: str,
    night_state: str,
) -> None:
    """Test the active price wakes at a midnight period boundary inside a night slot."""
    client = mock_engie_client.return_value
    client.async_get_tou_schedules.return_value = build_tou_schedules()
    client.async_get_prices.return_value = _two_period_prices(
        first_valid_to, second_valid_from, first_night_price
    )
    await setup_entry(hass, mock_config_entry)

    active_price_id = _tou_entity_id(
        entity_registry, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_current_price"
    )
    active_price = hass.states.get(active_price_id)
    assert active_price.state == initial_state
    assert active_price.attributes["next_transition"] == datetime(
        2026, 10, 3, 22, 0, tzinfo=BRUSSELS_TIME_ZONE
    )

    with _no_coordinator_refresh():
        freezer.tick(timedelta(hours=9))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        active_price = hass.states.get(active_price_id)
        assert active_price.state == night_state
        assert active_price.attributes["next_transition"] == datetime(
            2026, 10, 4, 0, 0, tzinfo=BRUSSELS_TIME_ZONE
        )
        assert float(active_price.attributes["next_price"]) == pytest.approx(0.13)

        freezer.tick(timedelta(hours=1, minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    active_price = hass.states.get(active_price_id)
    assert float(active_price.state) == pytest.approx(0.13)
    assert active_price.attributes["next_transition"] == datetime(
        2026, 10, 4, 7, 0, tzinfo=BRUSSELS_TIME_ZONE
    )
    assert float(active_price.attributes["next_price"]) == pytest.approx(0.20)
    assert client.async_get_prices.call_count == 1
    assert client.async_get_tou_schedules.call_count == 1
