"""Tests for the Duosida EV Charger config flow."""

from unittest.mock import AsyncMock

from duosida_ev import (
    DiscoveredCharger,
    DiscoveryError,
    DuosidaConnectionError,
    DuosidaTimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.duosida_ev.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_ID, HOST

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

OTHER_HOST = "192.168.1.101"


async def _start_flow(hass: HomeAssistant, next_step_id: str) -> ConfigFlowResult:
    """Start a user flow and pick a menu option."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": next_step_id}
    )


async def test_manual_flow(
    hass: HomeAssistant, mock_identify_charger: AsyncMock
) -> None:
    """Test setting up a charger from its IP address."""
    result = await _start_flow(hass, "manual")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Duosida EV Charger"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == DEVICE_ID
    mock_identify_charger.assert_awaited_once_with(HOST)


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(DuosidaConnectionError, "cannot_connect", id="connection"),
        pytest.param(DuosidaTimeoutError, "cannot_connect", id="timeout"),
        pytest.param(Exception, "unknown", id="unexpected"),
    ],
)
async def test_manual_flow_errors(
    hass: HomeAssistant,
    mock_identify_charger: AsyncMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test errors in the manual step, and recovering from them."""
    mock_identify_charger.side_effect = side_effect
    result = await _start_flow(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_identify_charger.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_flow_invalid_host(
    hass: HomeAssistant, mock_identify_charger: AsyncMock
) -> None:
    """Test a host name is refused: chargers are compared by IP address."""
    result = await _start_flow(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "charger.local"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}
    mock_identify_charger.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_flow_host_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_identify_charger: AsyncMock,
) -> None:
    """Test a configured charger is not contacted: it accepts one session."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_flow(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_identify_charger.assert_not_awaited()


@pytest.mark.usefixtures("mock_identify_charger")
async def test_manual_flow_updates_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a configured charger found at a new address gets the new address."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_flow(hass, "manual")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: OTHER_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: OTHER_HOST}


async def test_search_flow(
    hass: HomeAssistant,
    mock_discover_chargers: AsyncMock,
    mock_identify_charger: AsyncMock,
) -> None:
    """Test picking a charger found on the network."""
    result = await _start_flow(hass, "search")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search"
    # One probe per enabled network adapter, not only the default interface.
    mock_discover_chargers.assert_awaited_once_with(
        targets=["192.168.1.255"], identify=False
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Duosida EV Charger"
    assert result["data"] == {CONF_HOST: HOST}
    assert result["result"].unique_id == DEVICE_ID
    mock_identify_charger.assert_awaited_once_with(HOST)


async def test_search_flow_skips_configured_charger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discover_chargers: AsyncMock,
    mock_identify_charger: AsyncMock,
) -> None:
    """Test a configured charger is not contacted: it accepts one session."""
    mock_config_entry.add_to_hass(hass)
    mock_discover_chargers.return_value = [
        DiscoveredCharger(host=HOST),
        DiscoveredCharger(host=OTHER_HOST),
    ]

    result = await _start_flow(hass, "search")

    assert result["type"] is FlowResultType.FORM
    mock_identify_charger.assert_awaited_once_with(OTHER_HOST)


@pytest.mark.usefixtures("mock_discover_chargers", "mock_identify_charger")
async def test_search_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test picking a configured charger that moved to a new address."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={CONF_HOST: OTHER_HOST}
    )

    result = await _start_flow(hass, "search")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data == {CONF_HOST: HOST}


@pytest.mark.parametrize(
    ("discovered", "discovery_error", "identify_error"),
    [
        pytest.param([], None, None, id="nothing_found"),
        pytest.param(None, DiscoveryError, None, id="discovery_error"),
        pytest.param(
            [DiscoveredCharger(host=HOST)], None, DuosidaTimeoutError, id="no_identity"
        ),
    ],
)
async def test_search_flow_no_devices(
    hass: HomeAssistant,
    mock_discover_chargers: AsyncMock,
    mock_identify_charger: AsyncMock,
    discovered: list[DiscoveredCharger] | None,
    discovery_error: type[Exception] | None,
    identify_error: type[Exception] | None,
) -> None:
    """Test the flow aborts when no charger can be offered."""
    mock_discover_chargers.return_value = discovered
    mock_discover_chargers.side_effect = discovery_error
    mock_identify_charger.side_effect = identify_error

    result = await _start_flow(hass, "search")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
