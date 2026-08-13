"""Test the ENGIE Belgium integration setup."""

from unittest.mock import AsyncMock, MagicMock

from aioengiebelgium import (
    AccountRelation,
    CustomerAccount,
    CustomerAccountRelations,
    EngieBeAuthenticationError,
    EngieBeCommunicationError,
    PricesResponse,
)
import pytest

from homeassistant.components.engie_be.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import BAN, BAN_2, OFFTAKE_ONLY_EAN, build_prices, build_relations

from tests.common import MockConfigEntry


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
    ("side_effect", "expected_state", "expected_flows"),
    [
        pytest.param(
            EngieBeCommunicationError("boom"),
            ConfigEntryState.SETUP_RETRY,
            0,
            id="communication_error",
        ),
        pytest.param(
            EngieBeAuthenticationError("boom"),
            ConfigEntryState.SETUP_ERROR,
            1,
            id="auth_error",
        ),
    ],
)
async def test_setup_relations_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    expected_flows: int,
) -> None:
    """Test setup handles a failure of the customer-account-relations fetch."""
    mock_engie_client.return_value.async_get_customer_account_relations.side_effect = (
        side_effect
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    assert len(hass.config_entries.flow.async_progress()) == expected_flows


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expect_reauth"),
    [
        pytest.param(
            EngieBeCommunicationError("boom"),
            ConfigEntryState.SETUP_RETRY,
            False,
            id="communication_error",
        ),
        pytest.param(
            EngieBeAuthenticationError("boom"),
            ConfigEntryState.SETUP_ERROR,
            True,
            id="auth_error",
        ),
    ],
)
async def test_setup_prices_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    expect_reauth: bool,
) -> None:
    """Test setup handles a failure of the initial prices fetch."""
    mock_engie_client.return_value.async_get_prices.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows) == expect_reauth


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
    assert "no previous data" in caplog.text
    assert BAN_2 not in caplog.text
    assert BAN_2[-4:] in caplog.text


async def test_all_bans_fail_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test setup retries when every BAN fails on the first refresh."""
    mock_engie_client.return_value.async_get_customer_account_relations.return_value = (
        build_relations(BAN, BAN_2)
    )
    mock_engie_client.return_value.async_get_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_service_point_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test setup triggers reauth when a service-point lookup fails to authenticate."""
    mock_engie_client.return_value.async_get_service_point.side_effect = (
        EngieBeAuthenticationError("boom")
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_setup_no_active_agreements(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test setup fails permanently when there are no active business agreements."""
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

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


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

    ban_2_device = device_registry.async_get_device(identifiers={(DOMAIN, BAN_2)})
    assert ban_2_device is not None
    assert not er.async_entries_for_device(entity_registry, ban_2_device.id)

    ban_device = device_registry.async_get_device(identifiers={(DOMAIN, BAN)})
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
    assert mock_config_entry.data["username"] == "user@example.com"
    assert mock_config_entry.data["mfa_method"] == "sms"


async def test_unexpected_service_point_error_aborts_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected non-EngieBeError from a service-point lookup aborts the refresh and retries."""
    mock_engie_client.return_value.async_get_service_point.side_effect = ValueError(
        "boom"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Unexpected error fetching engie_be data" in caplog.text


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
