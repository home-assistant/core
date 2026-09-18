"""Test the ADS integration setup."""

from collections.abc import Callable
from unittest.mock import MagicMock

import pyads
import pytest

from homeassistant.components.ads import (
    CONF_ADS_TYPE,
    CONF_ADS_VALUE,
    SERVICE_WRITE_DATA_BY_NAME,
)
from homeassistant.components.ads.const import (
    CONF_ADS_VAR,
    CONF_LOCAL_NET_ID,
    DOMAIN,
    AdsType,
)
from homeassistant.components.ads.entity import AdsEntity
from homeassistant.components.ads.hub import AdsHub
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import MockPyadsLocalNetId
from .const import AMS_NET_ID, AUTO_NET_ID, LOCAL_NET_ID

from tests.common import MockConfigEntry

YAML_CONFIG = {
    DOMAIN: {
        CONF_DEVICE: AMS_NET_ID,
        CONF_IP_ADDRESS: "192.168.1.10",
        CONF_PORT: 851,
    }
}


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test setting up and unloading the config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, AdsHub)
    mock_pyads_connection.return_value.open.assert_called_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_pyads_connection.return_value.close.assert_called_once()


async def test_reload_resubscribes_yaml_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test a reload rebinds YAML-configured entities to the new hub."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    original_hub = mock_config_entry.runtime_data
    entity = AdsEntity(original_hub, "test", "GVL.test")
    entity.hass = hass
    entity.entity_id = "binary_sensor.test"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    new_hub = mock_config_entry.runtime_data
    assert new_hub is not original_hub
    assert entity._ads_hub is new_hub
    assert entity in new_hub.devices


async def test_setup_with_local_net_id(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test setting up the config entry with a local AMS NetID configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=AMS_NET_ID,
        data={
            CONF_DEVICE: AMS_NET_ID,
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_PORT: 851,
            CONF_LOCAL_NET_ID: LOCAL_NET_ID,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_pyads_local_net_id.open_port.assert_called_once()
    mock_pyads_local_net_id.set_local_address.assert_called_once_with(LOCAL_NET_ID)
    mock_pyads_local_net_id.close_port.assert_called_once()


async def test_remove_entry_restores_local_net_id(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test removing the entry restores the original local AMS NetID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=AMS_NET_ID,
        data={
            CONF_DEVICE: AMS_NET_ID,
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_PORT: 851,
            CONF_LOCAL_NET_ID: LOCAL_NET_ID,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    mock_pyads_local_net_id.set_local_address.assert_called_with(AUTO_NET_ID)


async def test_remove_entry_without_local_net_id_is_noop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
    mock_pyads_local_net_id: MockPyadsLocalNetId,
) -> None:
    """Test removing an entry without a configured local NetID leaves pyads alone."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_pyads_local_net_id.open_port.assert_not_called()


async def test_setup_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test the entry is retried when the device is unreachable."""
    mock_pyads_connection.return_value.read_state.side_effect = pyads.ADSError(
        text="timeout"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_pyads_connection.return_value.close.assert_called_once()


async def test_setup_not_ready_router_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test the entry is retried when the local AMS router is unavailable."""
    mock_pyads_connection.return_value.open.side_effect = RuntimeError(
        "Failed to open port on AMS router."
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test YAML is imported and a deprecation issue is raised."""
    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deprecation issue is raised when an entry already exists."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")


@pytest.mark.parametrize(
    ("configure_mock", "reason"),
    [
        pytest.param(
            lambda mock: setattr(
                mock.return_value.read_state,
                "side_effect",
                pyads.ADSError(text="timeout"),
            ),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            lambda mock: setattr(mock, "side_effect", ValueError("no valid netid")),
            "invalid_net_id",
            id="invalid_net_id",
        ),
        pytest.param(
            lambda mock: setattr(
                mock.return_value.read_state, "side_effect", RuntimeError
            ),
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_yaml_import_failed(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    issue_registry: ir.IssueRegistry,
    configure_mock: Callable[[MagicMock], None],
    reason: str,
) -> None:
    """Test a failed import raises an integration issue."""
    configure_mock(mock_pyads_connection)

    assert await async_setup_component(hass, DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
    assert not issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")


async def test_write_data_by_name(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pyads_connection: MagicMock,
) -> None:
    """Test the write_data_by_name service writes to the connected device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_WRITE_DATA_BY_NAME,
        {
            CONF_ADS_VAR: "GVL.test_var",
            CONF_ADS_TYPE: AdsType.INT,
            CONF_ADS_VALUE: 42,
        },
        blocking=True,
    )

    mock_pyads_connection.return_value.write_by_name.assert_called_once_with(
        "GVL.test_var", 42, pyads.PLCTYPE_INT
    )


async def test_write_data_by_name_not_loaded(hass: HomeAssistant) -> None:
    """Test the write_data_by_name service raises when no entry is loaded."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="not set up"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_WRITE_DATA_BY_NAME,
            {
                CONF_ADS_VAR: "GVL.test_var",
                CONF_ADS_TYPE: AdsType.INT,
                CONF_ADS_VALUE: 42,
            },
            blocking=True,
        )
