"""Test the ENGIE Belgium sensor platform."""

from collections.abc import Callable, Mapping
import dataclasses
from datetime import timedelta
from unittest.mock import MagicMock

from aioengiebelgium import (
    AccountRelation,
    BusinessAgreement,
    ConsumptionAddress,
    CustomerAccount,
    CustomerAccountRelations,
    EanPrices,
    EngieBeAuthenticationError,
    EngieBeCommunicationError,
    EngieBeError,
    PricePeriod,
    PriceSlot,
    PricesResponse,
    ServicePoint,
    bare_ean,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.engie_be.const import DOMAIN, PRICES_SCAN_INTERVAL
from homeassistant.components.engie_be.coordinator import EngieBePricesData
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    BAN,
    BAN_2,
    OFFTAKE_INJECTION_EAN,
    OFFTAKE_ONLY_EAN,
    build_prices,
    build_relations,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
) -> None:
    """Test the energy-price sensors for an offtake-only and a dual-direction EAN."""
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
    """Test slot-aware translation keys drive friendly names while unique_ids keep the raw slot code."""
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

    fallback_unique_id = f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_S_TOU1_OFFTAKE_WEEKEND"
    fallback_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, fallback_unique_id
    )
    assert fallback_entity_id is not None
    fallback_state = hass.states.get(fallback_entity_id)
    assert fallback_state is not None
    assert fallback_state.name.endswith("Electricity offtake price (weekend)")

    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_EN"
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

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
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


SECOND_ELECTRICITY_EAN = "541448820000000003_ID1"


def _single_period_prices(ean: str) -> EanPrices:
    """Build a single-period, offtake-only EanPrices for the given EAN."""
    return EanPrices(
        ean=ean,
        periods=(
            PricePeriod(
                valid_from="2000-01-01",
                valid_to="2099-12-31",
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
    eans = (OFFTAKE_INJECTION_EAN, SECOND_ELECTRICITY_EAN)
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
    assert names[OFFTAKE_INJECTION_EAN] != names[SECOND_ELECTRICITY_EAN]


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(EngieBeCommunicationError("boom"), id="communication_error"),
        pytest.param(EngieBeAuthenticationError("boom"), id="auth_error"),
    ],
)
async def test_type_fallback_when_service_point_lookup_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    exception: Exception,
) -> None:
    """Test a failed service-point lookup falls back to the untyped entity name."""
    mock_engie_client.return_value.async_get_service_point.side_effect = [
        exception,
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
        pytest.param("2026-08-01", "2026-09-01", id="inside-window"),
        pytest.param("2026-08-13", "2026-09-01", id="first-day-inclusive"),
        pytest.param(
            "2026-08-01T00:00:00",
            "2026-09-01T00:00:00",
            id="datetime-format-dates",
        ),
    ],
)
async def test_period_window_creates_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    valid_from: str,
    valid_to: str,
) -> None:
    """Test sensors are created with a numeric state for a period covering today."""
    freezer.move_to("2026-08-13T12:00:00+02:00")
    mock_engie_client.return_value.async_get_prices.return_value = build_prices(
        valid_from=valid_from, valid_to=valid_to
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
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


@pytest.mark.parametrize(
    ("valid_from", "valid_to"),
    [
        pytest.param("2026-08-01", "2026-08-13", id="last-day-exclusive"),
        pytest.param("2026-01-01", "2026-02-01", id="expired-window"),
        pytest.param("not-a-date", "2026-09-01", id="malformed-dates"),
    ],
)
async def test_period_window_skips_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    valid_from: str,
    valid_to: str,
) -> None:
    """Test no sensors are created when no period covers today (locks in exclusive valid_to)."""
    freezer.move_to("2026-08-13T12:00:00+02:00")
    mock_engie_client.return_value.async_get_prices.return_value = build_prices(
        valid_from=valid_from, valid_to=valid_to
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entity_entries == []


def _degraded_slots_empty() -> EngieBePricesData:
    """Return prices data with no slots or EANs at all."""
    return EngieBePricesData(slots={}, eans=())


def _degraded_period_expired() -> EngieBePricesData:
    """Return prices data whose only period for the EAN has expired."""
    return EngieBePricesData(slots={}, eans=(OFFTAKE_ONLY_EAN,))


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
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
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
        valid_from="2026-08-14", valid_to="2026-09-01"
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )

    freezer.tick(timedelta(days=1, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
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
        time_of_use_slot_code="S_TOU1_OFFTAKE_NIGHT",
        price_value=0.09,
        price_value_excl_vat=0.084906,
    )
    mock_engie_client.return_value.async_get_prices.return_value = _add_offtake_slot(
        build_prices(), OFFTAKE_INJECTION_EAN, extra_slot
    )
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    count_after = len(
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
    )
    assert count_after == count_before + 2

    incl_vat_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_S_TOU1_OFFTAKE_NIGHT"
    )
    excl_vat_id = entity_registry.async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{BAN}_{OFFTAKE_INJECTION_EAN}_offtake_S_TOU1_OFFTAKE_NIGHT_excl_vat",
    )
    assert incl_vat_id is not None
    assert excl_vat_id is not None


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

    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
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
    ban_2_prices = PricesResponse(
        items=(_single_period_prices(SECOND_ELECTRICITY_EAN),)
    )
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
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN_2}_{SECOND_ELECTRICITY_EAN}_offtake_TOTAL_HOURS"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name.endswith("Offtake price")
