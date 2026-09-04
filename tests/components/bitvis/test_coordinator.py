"""Tests for the Bitvis Power Hub coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from bitvis_protobuf.listener import FilterMac
import pytest

from homeassistant.components.bitvis.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import SECOND_DEVICE_MAC, TEST_DEVICE_MAC, patch_config_flow_connectivity

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("patch_shared_listener")


async def test_setup_registers_mac_filter_on_listener(
    init_integration: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test integration setup registers a MAC filter on the shared listener."""
    assert init_integration.state is ConfigEntryState.LOADED
    patch_shared_listener.start.assert_awaited_once_with(DEFAULT_PORT)
    patch_shared_listener.register.assert_called_once()
    registered_filter = patch_shared_listener.register.call_args[0][0]
    assert isinstance(registered_filter, FilterMac)
    assert registered_filter.mac_address == TEST_DEVICE_MAC


async def test_two_entries_share_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_second_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that two entries on the same port share one library listener."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_second_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_second_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_second_config_entry.state is ConfigEntryState.LOADED
    patch_shared_listener.start.assert_awaited_once_with(DEFAULT_PORT)
    assert patch_shared_listener.register.call_count == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    patch_shared_listener.stop.assert_not_called()

    assert await hass.config_entries.async_unload(mock_second_config_entry.entry_id)
    patch_shared_listener.stop.assert_awaited_once()


async def test_user_form_skips_port_bind_when_listener_exists(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test user flow skips port bind check when a listener already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.bitvis.config_flow.async_verify_udp_port_bindable",
            new_callable=AsyncMock,
        ) as mock_verify,
        patch_config_flow_connectivity(
            "192.168.1.101",
            mac_address=SECOND_DEVICE_MAC,
            use_real_listener_registry=True,
            shared_listener=patch_shared_listener,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.101",
            },
        )

    mock_verify.assert_not_awaited()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_setup_oserror_results_in_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: MagicMock,
) -> None:
    """Test that OSError from SharedListener.start results in SETUP_RETRY."""
    mock_shared_listener.start = AsyncMock(side_effect=OSError("port in use"))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_runtime_error_results_in_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: MagicMock,
) -> None:
    """Test that RuntimeError from SharedListener.register results in SETUP_ERROR."""
    mock_shared_listener.register.side_effect = RuntimeError("duplicate filter")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_shared_listener.unregister.assert_not_called()
