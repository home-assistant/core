"""Tests for the NX584 integration setup and YAML import."""

import asyncio
from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.nx584.const import (
    CONF_ENTITY_NAMESPACES,
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import TEST_HOST, TEST_PORT

from tests.common import MockConfigEntry

ALARM_YAML = {
    ALARM_CONTROL_PANEL_DOMAIN: {
        "platform": DOMAIN,
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_NAME: "House",
    }
}
BINARY_SENSOR_YAML = {
    BINARY_SENSOR_DOMAIN: {
        "platform": DOMAIN,
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_EXCLUDE_ZONES: [2],
        CONF_ZONE_TYPES: {3: "motion"},
    }
}


BOTH_YAML = ALARM_YAML | BINARY_SENSOR_YAML
NAMESPACED_YAML = {
    ALARM_CONTROL_PANEL_DOMAIN: {
        **ALARM_YAML[ALARM_CONTROL_PANEL_DOMAIN],
        CONF_ENTITY_NAMESPACE: "security",
    },
    BINARY_SENSOR_DOMAIN: {
        **BINARY_SENSOR_YAML[BINARY_SENSOR_DOMAIN],
        CONF_ENTITY_NAMESPACE: "zones",
    },
}


async def _async_setup_yaml(
    hass: HomeAssistant, hass_config: ConfigType, *domains: str
) -> None:
    """Set up the YAML domains one at a time, in the given order."""
    for domain in domains:
        assert await async_setup_component(hass, domain, hass_config)
        await hass.async_block_till_done()


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_watcher: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry sets up both platforms and stops the watcher on unload."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_client.return_value
    mock_client.assert_called_with(f"http://{TEST_HOST}:{TEST_PORT}")
    assert hass.states.get("alarm_control_panel.nx584")
    assert hass.states.get("binary_sensor.front")
    mock_watcher.return_value.start.assert_called_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_watcher.return_value.stop.assert_called_once()


@pytest.mark.usefixtures("mock_watcher")
async def test_setup_entry_ipv6_host(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test an IPv6 host is bracketed in the server URL."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "fe80::1", CONF_PORT: TEST_PORT},
        unique_id=f"fe80::1:{TEST_PORT}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_client.assert_called_with(f"http://[fe80::1]:{TEST_PORT}")


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(requests.exceptions.ConnectionError, id="cannot_connect"),
        pytest.param(requests.exceptions.Timeout, id="timeout"),
    ],
)
async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test the entry retries when the server cannot be reached."""
    mock_client.return_value.list_zones.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(requests.exceptions.ConnectionError, id="cannot_connect"),
        pytest.param(requests.exceptions.Timeout, id="timeout"),
    ],
)
@pytest.mark.usefixtures("mock_watcher")
async def test_setup_entry_zone_fetch_not_ready(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test the entry retries when the zones cannot be fetched, then sets up."""
    mock_client.return_value.get_version.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN) == []

    mock_client.return_value.get_version.side_effect = None
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.front")


@pytest.mark.usefixtures("mock_client", "mock_watcher", "mock_hass_config")
@pytest.mark.parametrize("hass_config", [ALARM_YAML])
async def test_import_alarm_only(
    hass: HomeAssistant, hass_config: ConfigType, issue_registry: ir.IssueRegistry
) -> None:
    """Test a YAML alarm panel alone imports and sets up both platforms."""
    await _async_setup_yaml(hass, hass_config, ALARM_CONTROL_PANEL_DOMAIN)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_NAME: "House",
    }
    assert hass.states.get("alarm_control_panel.house")
    assert sorted(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == [
        "binary_sensor.back",
        "binary_sensor.front",
        "binary_sensor.inside",
    ]
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_client", "mock_watcher", "mock_hass_config")
@pytest.mark.parametrize(
    "hass_config", [{ALARM_CONTROL_PANEL_DOMAIN: {"platform": DOMAIN}}]
)
async def test_import_alarm_default_name(
    hass: HomeAssistant, hass_config: ConfigType
) -> None:
    """Test a YAML alarm panel without a name keeps the default entity ID."""
    await _async_setup_yaml(hass, hass_config, ALARM_CONTROL_PANEL_DOMAIN)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == "localhost:5007"
    assert hass.states.get("alarm_control_panel.nx584")


@pytest.mark.usefixtures("mock_client", "mock_watcher", "mock_hass_config")
@pytest.mark.parametrize("hass_config", [BINARY_SENSOR_YAML])
async def test_import_binary_sensor_only(
    hass: HomeAssistant, hass_config: ConfigType, issue_registry: ir.IssueRegistry
) -> None:
    """Test YAML zone sensors alone import with their zone settings and an alarm."""
    await _async_setup_yaml(hass, hass_config, BINARY_SENSOR_DOMAIN)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data == {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    assert entries[0].options == {
        CONF_EXCLUDE_ZONES: [2],
        CONF_ZONE_TYPES: {"3": "motion"},
    }
    assert hass.states.async_entity_ids(ALARM_CONTROL_PANEL_DOMAIN) == [
        "alarm_control_panel.nx584"
    ]
    assert hass.states.get("binary_sensor.front").attributes["device_class"] == (
        "opening"
    )
    assert hass.states.get("binary_sensor.back") is None
    assert hass.states.get("binary_sensor.inside").attributes["device_class"] == (
        "motion"
    )
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_client", "mock_watcher", "mock_hass_config")
@pytest.mark.parametrize("hass_config", [BOTH_YAML])
@pytest.mark.parametrize(
    "domains",
    [
        pytest.param(
            (ALARM_CONTROL_PANEL_DOMAIN, BINARY_SENSOR_DOMAIN), id="alarm_first"
        ),
        pytest.param(
            (BINARY_SENSOR_DOMAIN, ALARM_CONTROL_PANEL_DOMAIN),
            id="binary_sensor_first",
        ),
    ],
)
async def test_import_both_platforms(
    hass: HomeAssistant, hass_config: ConfigType, domains: tuple[str, str]
) -> None:
    """Test both YAML platforms of one server merge into a single entry."""
    await _async_setup_yaml(hass, hass_config, *domains)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_NAME: "House",
    }
    assert entries[0].options == {
        CONF_EXCLUDE_ZONES: [2],
        CONF_ZONE_TYPES: {"3": "motion"},
    }
    assert hass.states.async_entity_ids(ALARM_CONTROL_PANEL_DOMAIN) == [
        "alarm_control_panel.house"
    ]
    assert sorted(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == [
        "binary_sensor.front",
        "binary_sensor.inside",
    ]
    assert hass.states.get("binary_sensor.inside").attributes["device_class"] == (
        "motion"
    )


@pytest.mark.usefixtures("mock_client", "mock_watcher", "mock_hass_config")
@pytest.mark.parametrize("hass_config", [BOTH_YAML])
async def test_import_both_platforms_at_once(
    hass: HomeAssistant, hass_config: ConfigType
) -> None:
    """Test both YAML platforms set up concurrently still merge into one entry."""
    assert all(
        await asyncio.gather(
            async_setup_component(hass, ALARM_CONTROL_PANEL_DOMAIN, hass_config),
            async_setup_component(hass, BINARY_SENSOR_DOMAIN, hass_config),
        )
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_NAME] == "House"
    assert entries[0].options[CONF_EXCLUDE_ZONES] == [2]


@pytest.mark.usefixtures("mock_client", "mock_watcher", "mock_hass_config")
@pytest.mark.parametrize("hass_config", [NAMESPACED_YAML])
@pytest.mark.parametrize(
    "domains",
    [
        pytest.param(
            (ALARM_CONTROL_PANEL_DOMAIN, BINARY_SENSOR_DOMAIN), id="alarm_first"
        ),
        pytest.param(
            (BINARY_SENSOR_DOMAIN, ALARM_CONTROL_PANEL_DOMAIN),
            id="binary_sensor_first",
        ),
    ],
)
async def test_import_entity_namespaces(
    hass: HomeAssistant, hass_config: ConfigType, domains: tuple[str, str]
) -> None:
    """Test the YAML entity namespace of each platform keeps its entity IDs."""
    await _async_setup_yaml(hass, hass_config, *domains)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_ENTITY_NAMESPACES] == {
        ALARM_CONTROL_PANEL_DOMAIN: "security",
        BINARY_SENSOR_DOMAIN: "zones",
    }
    expected_entity_ids = {
        ALARM_CONTROL_PANEL_DOMAIN: ["alarm_control_panel.security_house"],
        BINARY_SENSOR_DOMAIN: [
            "binary_sensor.zones_front",
            "binary_sensor.zones_inside",
        ],
    }
    for domain, entity_ids in expected_entity_ids.items():
        assert sorted(hass.states.async_entity_ids(domain)) == entity_ids

    # The namespaces are stored, so a reload keeps the entity IDs.
    assert await hass.config_entries.async_reload(entries[0].entry_id)
    await hass.async_block_till_done()
    for domain, entity_ids in expected_entity_ids.items():
        assert sorted(hass.states.async_entity_ids(domain)) == entity_ids


@pytest.mark.usefixtures("mock_watcher", "mock_hass_config")
@pytest.mark.parametrize("hass_config", [BOTH_YAML])
async def test_import_cannot_connect(
    hass: HomeAssistant,
    hass_config: ConfigType,
    mock_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an unreachable server during import raises a repair issue."""
    mock_client.return_value.list_zones.side_effect = (
        requests.exceptions.ConnectionError
    )
    await _async_setup_yaml(
        hass, hass_config, ALARM_CONTROL_PANEL_DOMAIN, BINARY_SENSOR_DOMAIN
    )

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_cannot_connect"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_watcher", "mock_hass_config")
@pytest.mark.parametrize("hass_config", [ALARM_YAML])
async def test_import_flow_in_progress(
    hass: HomeAssistant,
    hass_config: ConfigType,
    mock_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an import for a server with a user flow in progress raises no issue."""
    mock_client.return_value.list_zones.side_effect = (
        requests.exceptions.ConnectionError
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The failed attempt leaves the user flow open with the server unique ID.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT}
    )
    assert result["errors"] == {"base": "cannot_connect"}
    mock_client.return_value.list_zones.side_effect = None

    await _async_setup_yaml(hass, hass_config, ALARM_CONTROL_PANEL_DOMAIN)

    assert hass.config_entries.async_entries(DOMAIN) == []
    assert not issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_already_in_progress"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
