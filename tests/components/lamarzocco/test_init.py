"""Test initialization of lamarzocco."""

from unittest.mock import AsyncMock, MagicMock, patch

from pylamarzocco.const import FirmwareType
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
import pytest
from websockets.protocol import State

from homeassistant.components.lamarzocco.config_flow import CONF_MACHINE
from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_TOKEN,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import USER_INPUT, async_init_integration, get_bluetooth_service_info

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the La Marzocco configuration entry not ready."""
    mock_lamarzocco.get_config.side_effect = RequestNotSuccessful("")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_lamarzocco.get_config.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test auth error during setup."""
    mock_lamarzocco.get_config.side_effect = AuthFail("")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(mock_lamarzocco.get_config.mock_calls) == 1

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


async def test_v1_migration(
    hass: HomeAssistant,
    mock_cloud_client: MagicMock,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test v1 -> v2 Migration."""
    common_data = {
        **USER_INPUT,
        CONF_HOST: "host",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
    }
    entry_v1 = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=mock_lamarzocco.serial_number,
        data={
            **common_data,
            CONF_MACHINE: mock_lamarzocco.serial_number,
        },
    )

    entry_v1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry_v1.entry_id)
    await hass.async_block_till_done()

    assert entry_v1.version == 2
    assert dict(entry_v1.data) == {
        **common_data,
        CONF_NAME: "GS3",
        CONF_MODEL: mock_lamarzocco.model,
        CONF_TOKEN: "token",
    }


async def test_migration_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_client: MagicMock,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test errors during migration."""

    mock_cloud_client.get_customer_fleet.side_effect = RequestNotSuccessful("Error")

    entry_v1 = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        unique_id=mock_lamarzocco.serial_number,
        data={
            **USER_INPUT,
            CONF_MACHINE: mock_lamarzocco.serial_number,
        },
    )
    entry_v1.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry_v1.entry_id)
    assert entry_v1.state is ConfigEntryState.MIGRATION_ERROR


async def test_config_flow_entry_migration_downgrade(
    hass: HomeAssistant,
) -> None:
    """Test that config entry fails setup if the version is from the future."""
    entry = MockConfigEntry(domain=DOMAIN, version=3)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_bluetooth_is_set_from_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Check we can fill a device from discovery info."""

    service_info = get_bluetooth_service_info(
        mock_lamarzocco.model, mock_lamarzocco.serial_number
    )
    with (
        patch(
            "homeassistant.components.lamarzocco.async_discovered_service_info",
            return_value=[service_info],
        ) as discovery,
        patch(
            "homeassistant.components.lamarzocco.coordinator.LaMarzoccoMachine"
        ) as init_device,
    ):
        await async_init_integration(hass, mock_config_entry)
    discovery.assert_called_once()
    init_device.assert_called_once()
    _, kwargs = init_device.call_args
    assert kwargs["bluetooth_client"] is not None
    assert mock_config_entry.data[CONF_NAME] == service_info.name
    assert mock_config_entry.data[CONF_MAC] == service_info.address


async def test_websocket_closed_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
) -> None:
    """Test the websocket is closed on unload."""
    with patch(
        "homeassistant.components.lamarzocco.LaMarzoccoLocalClient",
        autospec=True,
    ) as local_client:
        client = local_client.return_value
        client.websocket = AsyncMock()
        client.websocket.state = State.OPEN
        await async_init_integration(hass, mock_config_entry)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        client.websocket.close.assert_called_once()


@pytest.mark.parametrize(
    ("version", "issue_exists"), [("v3.5-rc6", False), ("v3.3-rc4", True)]
)
async def test_gateway_version_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
    version: str,
    issue_exists: bool,
) -> None:
    """Make sure we get the issue for certain gateway firmware versions."""
    mock_lamarzocco.firmware[FirmwareType.GATEWAY].current_version = version

    await async_init_integration(hass, mock_config_entry)

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "unsupported_gateway_firmware")
    assert (issue is not None) == issue_exists
