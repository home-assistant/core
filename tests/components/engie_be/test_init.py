"""Test the ENGIE Belgium integration setup."""

import asyncio
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, MagicMock

from aioengiebelgium import (
    AccountRelation,
    CustomerAccount,
    CustomerAccountRelations,
    EnergyContractsResponse,
    EngieBeAuthenticationError,
    EngieBeCommunicationError,
    PricesResponse,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.engie_be.const import CONTRACTS_RETRY_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    BAN,
    BAN_2,
    OFFTAKE_ONLY_EAN,
    build_contracts,
    build_prices,
    build_relations,
)

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_engie_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(EngieBeCommunicationError("boom"), id="communication_error"),
        pytest.param(EngieBeAuthenticationError("boom"), id="auth_error"),
    ],
)
async def test_setup_relations_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    side_effect: Exception,
) -> None:
    """Test setup handles a failure of the customer-account-relations fetch."""
    mock_engie_client.return_value.async_get_customer_account_relations.side_effect = (
        side_effect
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(EngieBeCommunicationError("boom"), id="communication_error"),
        pytest.param(EngieBeAuthenticationError("boom"), id="auth_error"),
    ],
)
async def test_setup_prices_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    side_effect: Exception,
) -> None:
    """Test setup succeeds with a device but no entities when the initial prices fetch fails."""
    mock_engie_client.return_value.async_get_prices.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, BAN), mock_config_entry.entry_id
        )
        is not None
    )
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_partial_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup comes up when only one of two BANs succeeds on the first refresh."""
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

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN_2}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
        )
        is None
    )
    assert "Error fetching" in caplog.text
    assert BAN_2 not in caplog.text
    assert BAN_2[-4:] in caplog.text


async def test_all_households_loaded_despite_prices_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup succeeds with devices but no entities when every household's first refresh fails."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )
    mock_engie_client.return_value.async_get_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 2
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_setup_without_active_agreements(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup succeeds without devices or entities when there are no active business agreements."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        CustomerAccountRelations(
            accounts=(
                AccountRelation(
                    id="account-1",
                    admin=True,
                    customer_account=CustomerAccount(
                        customer_account_number="can-1",
                        business_agreements=(),
                    ),
                ),
            )
        )
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_device_created_for_household_without_prices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a household device is registered even when its prices are empty."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )
    mock_engie_client.return_value.async_get_prices.side_effect = [
        build_prices(),
        PricesResponse(items=()),
    ]
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 2
    assert all(
        device.entry_type is dr.DeviceEntryType.SERVICE for device in device_entries
    )

    ban_2_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BAN_2), mock_config_entry.entry_id
    )
    assert ban_2_device is not None
    assert not er.async_entries_for_device(entity_registry, ban_2_device.id)

    ban_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, BAN), mock_config_entry.entry_id
    )
    assert ban_device is not None
    assert er.async_entries_for_device(entity_registry, ban_device.id)


async def test_token_refresh_skips_unchanged_tokens(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test the on_token_refresh callback is a no-op when tokens are unchanged."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    listener = AsyncMock()
    mock_config_entry.add_update_listener(listener)

    on_token_refresh = mock_engie_client.call_args.kwargs["on_token_refresh"]

    await on_token_refresh("access-token", "refresh-token")
    await hass.async_block_till_done()

    listener.assert_not_called()
    assert mock_config_entry.data["access_token"] == "access-token"
    assert mock_config_entry.data["refresh_token"] == "refresh-token"


async def test_token_refresh_persists_tokens(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test the on_token_refresh callback persists rotated tokens to entry.data."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    listener = AsyncMock()
    mock_config_entry.add_update_listener(listener)

    on_token_refresh = mock_engie_client.call_args.kwargs["on_token_refresh"]

    await on_token_refresh("rotated-access", "rotated-refresh")
    await hass.async_block_till_done()

    listener.assert_called_once()
    assert mock_config_entry.data["access_token"] == "rotated-access"
    assert mock_config_entry.data["refresh_token"] == "rotated-refresh"
    assert mock_config_entry.data["email"] == "user@example.com"
    assert mock_config_entry.data["mfa_method"] == "sms"


async def test_unexpected_service_point_error_does_not_prevent_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected non-EngieBeError from a service-point lookup leaves the household without entities but still loads the entry."""
    mock_engie_client.return_value.async_get_service_point.side_effect = ValueError(
        "boom"
    )
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Unexpected error fetching" in caplog.text
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, BAN), mock_config_entry.entry_id
        )
        is not None
    )
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


async def test_household_is_a_single_service_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a household's EANs share one SERVICE device instead of per-meter devices."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 1

    household_device = device_entries[0]
    assert household_device.identifiers == {(DOMAIN, BAN)}
    assert household_device.entry_type is dr.DeviceEntryType.SERVICE
    assert household_device.via_device_id is None


@pytest.mark.parametrize(
    ("ban", "expected"),
    [
        pytest.param(BAN, True, id="dynamic"),
        pytest.param(BAN_2, False, id="fixed"),
    ],
)
async def test_epex_entities_only_for_dynamic_households(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    ban: str,
    expected: bool,
) -> None:
    """Test EPEX entities appear only on households with a dynamic tariff."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )

    def _contracts(queried_ban: str) -> EnergyContractsResponse:
        return build_contracts(dynamic=queried_ban == BAN)

    mock_engie_client.return_value.async_get_energy_contracts.side_effect = _contracts
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{ban}_epex_current_hour"
    )
    assert (sensor_entity_id is not None) is expected
    binary_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{ban}_epex_tomorrow_available"
    )
    assert (binary_entity_id is not None) is expected


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(EngieBeCommunicationError("boom"), id="communication_error"),
        pytest.param(EngieBeAuthenticationError("boom"), id="auth_error"),
    ],
)
async def test_contracts_failure_loads_without_epex(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception,
) -> None:
    """Test a contracts fetch failure loads the entry with price sensors but no EPEX entities."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.engie_be")
    mock_engie_client.return_value.async_get_energy_contracts.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Tariff lookup failed" in caplog.text
    assert "Fetching energy contracts for" in caplog.text
    assert BAN not in caplog.text
    assert BAN[-4:] in caplog.text
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is None
    )


async def test_contracts_retry_adds_epex_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    frozen_afternoon: None,
) -> None:
    """Test a successful classification retry adds the EPEX entities."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    def _dynamic_contracts(_ban: str) -> EnergyContractsResponse:
        return build_contracts(dynamic=True)

    client.async_get_energy_contracts.side_effect = _dynamic_contracts
    freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert client.async_get_energy_contracts.call_count == 2
    sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_current_hour"
    )
    assert sensor_entity_id is not None
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.15)
    assert (
        entity_registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
        )
        is not None
    )


async def test_newly_dynamic_household_gets_entities_while_another_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    frozen_afternoon: None,
) -> None:
    """Test a household classified while another still retries gets its EPEX entities."""
    client = mock_engie_client.return_value
    client.async_get_customer_account_relations.return_value = build_relations(
        BAN, BAN_2
    )
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is None
    )

    def _dynamic_for_ban(queried_ban: str) -> EnergyContractsResponse:
        if queried_ban == BAN_2:
            raise EngieBeCommunicationError("boom")
        return build_contracts(dynamic=True)

    client.async_get_energy_contracts.side_effect = _dynamic_for_ban
    freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    sensor_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_current_hour"
    )
    assert sensor_entity_id is not None
    state = hass.states.get(sensor_entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.15)
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN_2}_epex_current_hour"
        )
        is None
    )

    client.async_get_energy_contracts.side_effect = lambda _ban: build_contracts()
    freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.epex is not None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN_2}_epex_current_hour"
        )
        is None
    )


async def test_contracts_failure_keeps_retrying(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a classification retry that fails again schedules the next one."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert client.async_get_energy_contracts.call_count == 1

    for _ in range(2):
        freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert client.async_get_energy_contracts.call_count == 3
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is None
    )


async def test_contracts_retry_only_queries_pending_households(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test each retry queries only the households whose tariff is still unknown."""
    client = mock_engie_client.return_value
    client.async_get_customer_account_relations.return_value = build_relations(
        BAN, BAN_2
    )

    def _contracts(queried_ban: str) -> EnergyContractsResponse:
        if queried_ban == BAN_2:
            raise EngieBeCommunicationError("boom")
        return build_contracts()

    client.async_get_energy_contracts.side_effect = _contracts
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    client.async_get_energy_contracts.reset_mock()

    for _ in range(3):
        freezer.tick(CONTRACTS_RETRY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert [
        call.args[0] for call in client.async_get_energy_contracts.call_args_list
    ] == [BAN_2, BAN_2, BAN_2]


async def test_contracts_retry_stops_once_classified(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the retries stop once every household has a known tariff."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client.async_get_energy_contracts.side_effect = lambda _ban: build_contracts()
    for _ in range(3):
        freezer.tick(CONTRACTS_RETRY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert client.async_get_energy_contracts.call_count == 2


async def test_contracts_retry_stops_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading the entry stops the tariff retries."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for _ in range(3):
        freezer.tick(CONTRACTS_RETRY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert client.async_get_energy_contracts.call_count == 1


async def test_contracts_retry_in_flight_during_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    frozen_afternoon: None,
) -> None:
    """Test a retry that finishes after unload adds no entities and stops retrying."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    release = asyncio.Event()

    async def _slow_dynamic_contracts(_ban: str) -> EnergyContractsResponse:
        await release.wait()
        return build_contracts(dynamic=True)

    client.async_get_energy_contracts.side_effect = _slow_dynamic_contracts
    freezer.tick(CONTRACTS_RETRY_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_get_energy_contracts.call_count == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    for _ in range(3):
        freezer.tick(CONTRACTS_RETRY_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert client.async_get_energy_contracts.call_count == 2
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is None
    )


async def test_contracts_retry_resolving_fixed_shuts_down_epex(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a pending household that resolves to fixed releases the EPEX coordinator."""
    client = mock_engie_client.return_value
    client.async_get_energy_contracts.side_effect = EngieBeCommunicationError("boom")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.epex is not None

    client.async_get_energy_contracts.side_effect = lambda _ban: build_contracts()
    freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.epex is None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
        )
        is not None
    )


async def test_pending_household_does_not_release_epex_of_dynamic_household(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a retry that resolves the last pending household to fixed keeps the EPEX coordinator."""
    client = mock_engie_client.return_value
    client.async_get_customer_account_relations.return_value = build_relations(
        BAN, BAN_2
    )

    def _contracts(queried_ban: str) -> EnergyContractsResponse:
        if queried_ban == BAN_2:
            raise EngieBeCommunicationError("boom")
        return build_contracts(dynamic=True)

    client.async_get_energy_contracts.side_effect = _contracts
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN_2}_epex_current_hour"
        )
        is None
    )

    def _fixed_contracts(_queried_ban: str) -> EnergyContractsResponse:
        return build_contracts()

    client.async_get_energy_contracts.side_effect = _fixed_contracts
    freezer.tick(CONTRACTS_RETRY_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.runtime_data.epex is not None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is not None
    )
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN_2}_epex_current_hour"
        )
        is None
    )
