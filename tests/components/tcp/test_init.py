"""Tests for the TCP setup and the YAML import."""

from unittest.mock import MagicMock

from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.components.tcp.const import (
    DEFAULT_BUFFER_SIZE,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

YAML = {"platform": "tcp", "host": "test_host", "port": 12345, "payload": "status"}


async def test_setup_unload(hass: HomeAssistant, setup_tcp) -> None:
    """Test the entry creates both entities with value_on and unloads them."""
    entry = await setup_tcp(value_on="7.on")
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.test_name")
    assert hass.states.get("binary_sensor.test_name")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("sensor.test_name").state == STATE_UNAVAILABLE
    assert hass.states.get("binary_sensor.test_name").state == STATE_UNAVAILABLE


async def test_setup_without_value_on(hass: HomeAssistant, setup_tcp) -> None:
    """Test only the sensor is created without value_on."""
    await setup_tcp()
    assert hass.states.get("sensor.test_name")
    assert not hass.states.get("binary_sensor.test_name")


async def test_yaml_import(
    hass: HomeAssistant,
    mock_socket: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the YAML config is imported and the issue is created."""
    assert await async_setup_component(hass, "sensor", {"sensor": YAML})
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.data["timeout"] == DEFAULT_TIMEOUT
    assert entry.data["buffer_size"] == DEFAULT_BUFFER_SIZE
    assert hass.states.get("sensor.tcp_sensor").state == "123"
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, "deprecated_yaml_tcp")
    assert entry.title == DEFAULT_NAME


async def test_yaml_import_keeps_name(
    hass: HomeAssistant, mock_socket: MagicMock
) -> None:
    """Test the legacy name is used as the entry title."""
    assert await async_setup_component(
        hass, "sensor", {"sensor": {**YAML, "name": "Legacy"}}
    )
    await hass.async_block_till_done()

    (entry,) = hass.config_entries.async_entries(DOMAIN)
    assert entry.title == "Legacy"
    assert "name" not in entry.data
    assert hass.states.get("sensor.legacy").state == "123"


async def test_yaml_import_cannot_connect(
    hass: HomeAssistant,
    mock_create_connection: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue created when the import fails."""
    mock_create_connection.side_effect = OSError("Boom")

    assert await async_setup_component(hass, "sensor", {"sensor": YAML})
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )


async def test_yaml_invalid(hass: HomeAssistant, mock_socket: MagicMock) -> None:
    """Test an invalid YAML config is not imported."""
    assert await async_setup_component(
        hass, "sensor", {"sensor": {"platform": "tcp", "porrt": 1234}}
    )
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(DOMAIN)
