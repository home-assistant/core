"""Test the ENGIE Belgium prices coordinator."""

from collections.abc import Callable, Mapping
from datetime import timedelta
from unittest.mock import MagicMock

from aioengiebelgium import (
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

from homeassistant.components.engie_be.const import DOMAIN, PRICES_SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import BAN, BAN_2, OFFTAKE_ONLY_EAN, build_relations

from tests.common import MockConfigEntry, async_fire_time_changed


def _build_prices(price_value: float) -> PricesResponse:
    """Build a prices response with one offtake slot for the given price."""
    return PricesResponse(
        items=(
            EanPrices(
                ean=OFFTAKE_ONLY_EAN,
                periods=(
                    PricePeriod(
                        valid_from="2000-01-01",
                        valid_to="2099-12-31",
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


def _entity_id(entity_registry: er.EntityRegistry, ban: str) -> str:
    """Return the entity_id for a BAN's offtake-only price sensor."""
    unique_id = f"{ban}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
    entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


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
        {BAN: _build_prices(0.1), BAN_2: _build_prices(0.2)}
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
        {BAN: _build_prices(0.3), BAN_2: EngieBeCommunicationError("boom")}
    )
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state_ban = hass.states.get(_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_entity_id(entity_registry, BAN_2))
    assert state_ban is not None
    assert state_ban_2 is not None
    assert state_ban.state == "0.3"
    assert state_ban_2.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(EngieBeCommunicationError("boom"), id="communication_error"),
        pytest.param(EngieBeAuthenticationError("boom"), id="auth_error"),
    ],
)
async def test_all_bans_fail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test all BANs failing on refresh makes every sensor unavailable."""
    await _setup_two_bans(hass, mock_config_entry, mock_engie_client)

    mock_engie_client.return_value.async_get_prices.side_effect = exception
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state_ban = hass.states.get(_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_entity_id(entity_registry, BAN_2))
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
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Unexpected error fetching" in caplog.text
    households = mock_config_entry.runtime_data.households
    assert households[BAN].prices.last_update_success is False
    assert households[BAN_2].prices.last_update_success is False


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
        {BAN: EngieBeCommunicationError("boom"), BAN_2: _build_prices(0.2)}
    )
    caplog.clear()
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count("Error fetching") == 1
    assert "recovered" not in caplog.text
    caplog.clear()

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {BAN: EngieBeCommunicationError("boom"), BAN_2: _build_prices(0.3)}
    )
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error fetching" not in caplog.text
    caplog.clear()

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {BAN: _build_prices(0.4), BAN_2: _build_prices(0.5)}
    )
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert caplog.text.count("recovered") == 1

    state_ban = hass.states.get(_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_entity_id(entity_registry, BAN_2))
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
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_engie_client.return_value.async_get_prices.side_effect = _prices_by_ban(
        {BAN: _build_prices(0.4), BAN_2: _build_prices(0.5)}
    )
    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state_ban = hass.states.get(_entity_id(entity_registry, BAN))
    state_ban_2 = hass.states.get(_entity_id(entity_registry, BAN_2))
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
    mock_engie_client.return_value.async_get_prices.return_value = _build_prices(0.1)
    mock_engie_client.return_value.async_get_service_point.side_effect = [
        EngieBeCommunicationError("boom"),
        ServicePoint(ean_energy_types={bare_ean(OFFTAKE_ONLY_EAN): "GAS"}),
    ]
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # the failure log masks the bare EAN's last four digits, not the shared _ID1 suffix
    assert "Fetching service point for …0001 failed" in caplog.text
    assert "…_ID1" not in caplog.text

    coordinator = mock_config_entry.runtime_data.households[BAN].prices
    assert bare_ean(OFFTAKE_ONLY_EAN) not in coordinator.ean_energy_types

    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_engie_client.return_value.async_get_service_point.call_count == 2
    assert coordinator.ean_energy_types[bare_ean(OFFTAKE_ONLY_EAN)] == "GAS"


async def test_service_point_success_without_ean_is_cached_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a successful fetch omitting the EAN is cached once and not retried."""
    mock_engie_client.return_value.async_get_prices.return_value = _build_prices(0.1)
    mock_engie_client.return_value.async_get_service_point.side_effect = lambda ean: (
        ServicePoint(ean_energy_types={})
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.households[BAN].prices
    assert coordinator.ean_energy_types[bare_ean(OFFTAKE_ONLY_EAN)] is None

    freezer.tick(PRICES_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_engie_client.return_value.async_get_service_point.call_count == 1
