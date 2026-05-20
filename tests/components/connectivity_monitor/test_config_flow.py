"""Test the Connectivity Monitor config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.connectivity_monitor.const import (
    CONF_ALERT_ACTION,
    CONF_ALERT_ACTION_DELAY,
    CONF_ALERT_ACTION_ENABLED,
    CONF_ALERT_DELAY,
    CONF_ALERT_GROUP,
    CONF_ALERTS_ENABLED,
    CONF_BLUETOOTH_ADDRESS,
    CONF_DNS_SERVER,
    CONF_ESPHOME_DEVICE_ID,
    CONF_HOST,
    CONF_INACTIVE_TIMEOUT,
    CONF_INTERVAL,
    CONF_MATTER_NODE_ID,
    CONF_PROTOCOL,
    CONF_TARGETS,
    CONF_ZHA_IEEE,
    DEFAULT_DNS_SERVER,
    DEFAULT_INACTIVE_TIMEOUT,
    DOMAIN,
    PROTOCOL_AD_DC,
    PROTOCOL_BLUETOOTH,
    PROTOCOL_ESPHOME,
    PROTOCOL_ICMP,
    PROTOCOL_MATTER,
    PROTOCOL_TCP,
    PROTOCOL_UDP,
    PROTOCOL_ZHA,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(autouse=True)
def mock_network_validation_probe() -> AsyncMock:
    """Default config-flow network validation to a successful probe."""
    with patch(
        "homeassistant.components.connectivity_monitor.config_flow."
        "NetworkProbe.async_update_target",
        AsyncMock(
            return_value={
                "connected": True,
                "latency": 3.2,
                "resolved_ip": "192.168.1.10",
                "mac_address": None,
            }
        ),
    ) as mock_probe:
        yield mock_probe


@pytest.fixture
def ignore_missing_translations(request: pytest.FixtureRequest) -> list[str]:
    """Ignore known missing config-flow translations in this integration."""
    if request.node.name == "test_import_flow_aborts_when_typed_entry_exists":
        return []

    if request.node.name.startswith("test_options_flow_"):
        return ["component.connectivity_monitor.options."]

    return ["component.connectivity_monitor.config."]


async def test_user_step_shows_device_type_selector(hass: HomeAssistant) -> None:
    """Test the initial user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None


async def test_network_flow_create_first_entry(
    hass: HomeAssistant,
) -> None:
    """Test creating the initial network monitor entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_type": "network"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.10",
            CONF_PROTOCOL: PROTOCOL_ICMP,
            "device_name": "Core Router",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dns"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "interval"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INTERVAL: 45}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Network Monitor"
    assert result["result"].unique_id == "connectivity_monitor_network"
    assert result["data"] == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.10",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Core Router",
                "alert_group": None,
                "alert_delay": 15,
                "alert_action": "",
                "alert_action_delay": 30,
            }
        ],
        CONF_INTERVAL: 45,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_network_flow_tcp_includes_port_step(hass: HomeAssistant) -> None:
    """Test creating a TCP target goes through the port step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_type": "network"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.20",
            CONF_PROTOCOL: PROTOCOL_TCP,
            "device_name": "Web Server",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "port"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"port": 443}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dns"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.20",
                CONF_PROTOCOL: PROTOCOL_TCP,
                "device_name": "Web Server",
                CONF_ALERT_GROUP: None,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION: "",
                CONF_ALERT_ACTION_DELAY: 30,
                "port": 443,
            }
        ],
        CONF_INTERVAL: 60,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_network_flow_active_directory_expands_targets(
    hass: HomeAssistant,
) -> None:
    """Test Active Directory setup expands into the expected TCP targets."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_type": "network"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.30",
            CONF_PROTOCOL: PROTOCOL_AD_DC,
            "device_name": "Domain Controller",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dns"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INTERVAL: 90}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Network Monitor"
    assert len(result["data"][CONF_TARGETS]) == 8
    assert all(
        target[CONF_HOST] == "192.168.1.30" for target in result["data"][CONF_TARGETS]
    )
    assert all(
        target[CONF_PROTOCOL] == PROTOCOL_TCP for target in result["data"][CONF_TARGETS]
    )
    assert {target["port"] for target in result["data"][CONF_TARGETS]} == {
        88,
        139,
        389,
        445,
        464,
        636,
        3268,
        3269,
    }


async def test_network_flow_invalid_dns_server(hass: HomeAssistant) -> None:
    """Test invalid DNS entry keeps the flow on the DNS step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_type": "network"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.15",
            CONF_PROTOCOL: PROTOCOL_ICMP,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DNS_SERVER: "not-an-ip"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dns"
    assert result["errors"] == {"base": "invalid_dns_server"}


async def test_network_flow_rejects_unreachable_first_entry(
    hass: HomeAssistant,
) -> None:
    """Test first network entry stays on DNS step when validation cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_type": "network"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.15",
            CONF_PROTOCOL: PROTOCOL_ICMP,
        },
    )

    with patch(
        "homeassistant.components.connectivity_monitor.config_flow."
        "NetworkProbe.async_update_target",
        AsyncMock(
            return_value={
                "connected": False,
                "latency": None,
                "resolved_ip": None,
                "mac_address": None,
            }
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dns"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_network_flow_updates_existing_typed_entry(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test adding another network device updates the existing typed entry."""
    network_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "network"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.2",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Access Point",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"
    assert mock_reload.await_count == 1
    assert network_config_entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.1",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Router",
            },
            {
                CONF_HOST: "192.168.1.2",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Access Point",
                "alert_group": None,
                "alert_delay": 15,
                "alert_action": "",
                "alert_action_delay": 30,
            },
        ],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_network_flow_rejects_unreachable_existing_entry(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test adding a network device to an existing entry requires a successful probe."""
    network_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_type": "network"}
    )

    with patch(
        "homeassistant.components.connectivity_monitor.config_flow."
        "NetworkProbe.async_update_target",
        AsyncMock(
            return_value={
                "connected": False,
                "latency": None,
                "resolved_ip": None,
                "mac_address": None,
            }
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.2",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Access Point",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "network"
    assert result["errors"] == {"base": "cannot_connect"}
    assert network_config_entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.1",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Router",
            }
        ],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_zha_flow_without_available_devices(hass: HomeAssistant) -> None:
    """Test the ZHA flow when no ZHA devices are available."""
    with patch(
        "homeassistant.components.connectivity_monitor.config_flow.async_get_zha_devices",
        AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "zha"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zha_device"
    assert result["errors"] == {"base": "no_zha_devices"}


@pytest.mark.parametrize(
    ("device_type", "getter_path", "expected_step", "expected_error"),
    [
        (
            "matter",
            "homeassistant.components.connectivity_monitor.config_flow.async_get_matter_devices",
            "matter_device",
            "no_matter_devices",
        ),
        (
            "esphome",
            "homeassistant.components.connectivity_monitor.config_flow.async_get_esphome_devices",
            "esphome_device",
            "no_esphome_devices",
        ),
        (
            "bluetooth",
            "homeassistant.components.connectivity_monitor.config_flow.async_get_bluetooth_devices",
            "bluetooth_device",
            "no_bluetooth_devices",
        ),
    ],
)
async def test_shared_device_flow_without_available_devices(
    hass: HomeAssistant,
    device_type: str,
    getter_path: str,
    expected_step: str,
    expected_error: str,
) -> None:
    """Test Matter, ESPHome, and Bluetooth flows report an error when no devices are found."""
    with patch(getter_path, AsyncMock(return_value=[])):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": device_type}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    (
        "device_type",
        "getter_path",
        "entry_unique_id",
        "entry_data",
        "expected_step",
        "expected_error",
    ),
    [
        (
            "zha",
            "homeassistant.components.connectivity_monitor.config_flow.async_get_zha_devices",
            "connectivity_monitor_zha",
            {
                CONF_TARGETS: [
                    {
                        CONF_PROTOCOL: PROTOCOL_ZHA,
                        CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                        CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                        "device_name": "Hallway Sensor",
                    }
                ],
                CONF_INTERVAL: 60,
                CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
            },
            "zha_device",
            "all_zha_devices_added",
        ),
        (
            "matter",
            "homeassistant.components.connectivity_monitor.config_flow.async_get_matter_devices",
            "connectivity_monitor_matter",
            {
                CONF_TARGETS: [
                    {
                        CONF_PROTOCOL: PROTOCOL_MATTER,
                        CONF_HOST: "matter:1-1234",
                        CONF_MATTER_NODE_ID: "1-1234",
                        "device_name": "Thermostat",
                    }
                ],
                CONF_INTERVAL: 60,
                CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
            },
            "matter_device",
            "all_matter_devices_added",
        ),
        (
            "esphome",
            "homeassistant.components.connectivity_monitor.config_flow.async_get_esphome_devices",
            "connectivity_monitor_esphome",
            {
                CONF_TARGETS: [
                    {
                        CONF_PROTOCOL: "ESPHOME",
                        CONF_HOST: "esphome:node-1",
                        CONF_ESPHOME_DEVICE_ID: "node-1",
                        "device_name": "Garage Node",
                    }
                ],
                CONF_INTERVAL: 60,
                CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
            },
            "esphome_device",
            "all_esphome_devices_added",
        ),
        (
            "bluetooth",
            "homeassistant.components.connectivity_monitor.config_flow.async_get_bluetooth_devices",
            "connectivity_monitor_bluetooth",
            {
                CONF_TARGETS: [
                    {
                        CONF_PROTOCOL: "BLUETOOTH",
                        CONF_HOST: "bluetooth:AA:BB:CC:DD:EE:FF",
                        CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                        "device_name": "Tracker",
                    }
                ],
                CONF_INTERVAL: 60,
                CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
            },
            "bluetooth_device",
            "all_bluetooth_devices_added",
        ),
    ],
)
async def test_shared_device_flow_when_all_devices_already_added(
    hass: HomeAssistant,
    device_type: str,
    getter_path: str,
    entry_unique_id: str,
    entry_data: dict,
    expected_step: str,
    expected_error: str,
) -> None:
    """Test shared-device flows report when every discovered device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Typed Monitor",
        unique_id=entry_unique_id,
        version=2,
        data=entry_data,
    )
    entry.add_to_hass(hass)

    if device_type == "zha":
        available_devices = [
            {"ieee": "00:11:22:33:44:55:66:77", "name": "Hallway Sensor"}
        ]
    elif device_type == "matter":
        available_devices = [{"node_id": "1-1234", "name": "Thermostat"}]
    elif device_type == "esphome":
        available_devices = [{"device_id": "node-1", "name": "Garage Node"}]
    else:
        available_devices = [{"bt_address": "AA:BB:CC:DD:EE:FF", "name": "Tracker"}]

    with patch(getter_path, AsyncMock(return_value=available_devices)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": device_type}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step
    assert result["errors"] == {"base": expected_error}


async def test_matter_flow_create_first_typed_entry(hass: HomeAssistant) -> None:
    """Test creating the initial Matter typed entry from discovery."""
    with patch(
        "homeassistant.components.connectivity_monitor.config_flow.async_get_matter_devices",
        AsyncMock(
            return_value=[
                {
                    "node_id": "1-1234",
                    "name": "Living Room Thermostat",
                    "model": "T1000",
                    "manufacturer": "Acme",
                }
            ]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "matter"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "matter_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_MATTER_NODE_ID: "1-1234"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "matter_configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_name": "Living Room Thermostat",
                CONF_ALERTS_ENABLED: False,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION_ENABLED: False,
                CONF_ALERT_ACTION_DELAY: 30,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "dns"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_INTERVAL: 75}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Matter Monitor"
    assert result["result"].unique_id == "connectivity_monitor_matter"
    assert result["data"] == {
        CONF_TARGETS: [
            {
                CONF_PROTOCOL: PROTOCOL_MATTER,
                CONF_HOST: "matter:1-1234",
                CONF_MATTER_NODE_ID: "1-1234",
                "device_name": "Living Room Thermostat",
                CONF_ALERT_GROUP: None,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION: "",
                CONF_ALERT_ACTION_DELAY: 30,
                "model": "T1000",
                "manufacturer": "Acme",
            }
        ],
        CONF_INTERVAL: 75,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_import_flow_aborts_when_typed_entry_exists(
    hass: HomeAssistant,
) -> None:
    """Test import aborts when the typed entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ZigBee Monitor",
        unique_id="connectivity_monitor_zha",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_PROTOCOL: PROTOCOL_ZHA,
                    CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                    CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                    "device_name": "Hallway Sensor",
                }
            ],
            CONF_INTERVAL: 60,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            "entry_type": "zha",
            CONF_TARGETS: [
                {
                    CONF_PROTOCOL: PROTOCOL_ZHA,
                    CONF_HOST: "zha:aa:bb:cc:dd:ee:ff:00",
                    CONF_ZHA_IEEE: "aa:bb:cc:dd:ee:ff:00",
                    "device_name": "Kitchen Sensor",
                }
            ],
            CONF_INTERVAL: 60,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_shows_network_menu(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test options flow opens on the menu step for a network entry."""
    network_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(network_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "menu"


async def test_options_flow_updates_general_settings(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test updating interval and DNS server through options flow."""
    network_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(
            network_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "settings"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "settings_menu"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "general"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "settings"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INTERVAL: 120,
                CONF_DNS_SERVER: "8.8.8.8",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert mock_reload.await_count == 1
    assert network_config_entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.1",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Router",
            }
        ],
        CONF_INTERVAL: 120,
        CONF_DNS_SERVER: "8.8.8.8",
    }


async def test_options_flow_updates_network_alert_settings(
    hass: HomeAssistant,
) -> None:
    """Test alert settings are updated for all targets of a network device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: PROTOCOL_ICMP,
                    "device_name": "Router",
                },
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: "TCP",
                    "port": 443,
                    "device_name": "Router",
                },
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)

    hass.states.async_set(
        "automation.router_recovery", "on", {"friendly_name": "Router Recovery"}
    )
    hass.services.async_register("notify", "family", lambda call: None)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "alerts"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "device_select"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"device": "192.168.1.1"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "alert_config"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_ALERTS_ENABLED: True,
                CONF_ALERT_GROUP: "family",
                CONF_ALERT_DELAY: 10,
                CONF_ALERT_ACTION_ENABLED: True,
                CONF_ALERT_ACTION: "automation.router_recovery",
                CONF_ALERT_ACTION_DELAY: 25,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert mock_reload.await_count == 1
    assert entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.1",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Router",
                CONF_ALERT_GROUP: "family",
                CONF_ALERT_DELAY: 10,
                CONF_ALERT_ACTION: "automation.router_recovery",
                CONF_ALERT_ACTION_DELAY: 25,
            },
            {
                CONF_HOST: "192.168.1.1",
                CONF_PROTOCOL: "TCP",
                "port": 443,
                "device_name": "Router",
                CONF_ALERT_GROUP: "family",
                CONF_ALERT_DELAY: 10,
                CONF_ALERT_ACTION: "automation.router_recovery",
                CONF_ALERT_ACTION_DELAY: 25,
            },
        ],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_options_flow_rename_network_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test renaming a network device updates targets and removes old device entries."""
    network_config_entry.add_to_hass(hass)
    old_device = device_registry.async_get_or_create(
        config_entry_id=network_config_entry.entry_id,
        identifiers={(DOMAIN, "192.168.1.1")},
        hw_version="192.168.1.1",
    )

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(
            network_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "rename"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "rename_device_select"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"device": "192.168.1.1"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "rename_host"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "router.local",
                "device_name": "Main Router",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert mock_reload.await_count == 1
    assert network_config_entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "router.local",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Main Router",
            }
        ],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }
    assert device_registry.async_get(old_device.id) is None


async def test_options_flow_rejects_blank_rename_host(
    hass: HomeAssistant,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test renaming a network device rejects a blank host."""
    network_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(network_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "rename"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"device": "192.168.1.1"}
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "   ",
            "device_name": "Ignored Name",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "rename_host"
    assert result["errors"] == {CONF_HOST: "invalid_host"}


async def test_options_flow_remove_network_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a network device removes all its targets and registry device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: PROTOCOL_ICMP,
                    "device_name": "Router",
                },
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: PROTOCOL_TCP,
                    "port": 443,
                    "device_name": "Router",
                },
                {
                    CONF_HOST: "192.168.1.2",
                    CONF_PROTOCOL: PROTOCOL_ICMP,
                    "device_name": "Access Point",
                },
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)
    removed_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "192.168.1.1")},
        hw_version="192.168.1.1",
    )

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "remove_device"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "remove_device"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"device": "192.168.1.1"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert mock_reload.await_count == 1
    assert entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.2",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Access Point",
            }
        ],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }
    assert device_registry.async_get(removed_device.id) is None


async def test_options_flow_remove_single_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test removing a single sensor leaves the rest of the device targets intact."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Network Monitor",
        unique_id="connectivity_monitor_network",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: PROTOCOL_ICMP,
                    "device_name": "Router",
                },
                {
                    CONF_HOST: "192.168.1.1",
                    CONF_PROTOCOL: PROTOCOL_TCP,
                    "port": 443,
                    "device_name": "Router",
                },
            ],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)
    tcp_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "192.168.1.1_TCP_443",
        config_entry=entry,
        original_name="Router - TCP 443",
    )

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "remove_sensor"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "remove_sensor"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"sensor": "192.168.1.1_TCP_443"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert mock_reload.await_count == 1
    assert entry.data == {
        CONF_TARGETS: [
            {
                CONF_HOST: "192.168.1.1",
                CONF_PROTOCOL: PROTOCOL_ICMP,
                "device_name": "Router",
            }
        ],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }
    assert entity_registry.async_get(tcp_entity.entity_id) is None


async def test_options_flow_cleanup_orphaned_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    network_config_entry: MockConfigEntry,
) -> None:
    """Test cleanup removes orphaned devices linked to the config entry."""
    network_config_entry.add_to_hass(hass)
    orphan = device_registry.async_get_or_create(
        config_entry_id=network_config_entry.entry_id,
        identifiers={(DOMAIN, "orphan-device")},
        hw_version="orphan-host",
    )
    kept = device_registry.async_get_or_create(
        config_entry_id=network_config_entry.entry_id,
        identifiers={(DOMAIN, "active-device")},
        hw_version="192.168.1.1",
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "active_sensor",
        config_entry=network_config_entry,
        device_id=kept.id,
        original_name="Active Sensor",
    )

    result = await hass.config_entries.options.async_init(network_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "cleanup"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cleanup_done"
    assert device_registry.async_get(orphan.id) is None
    assert device_registry.async_get(kept.id) is not None


@pytest.mark.parametrize(
    (
        "entry_unique_id",
        "target",
        "selection_step",
        "selection_key",
        "selection_value",
        "config_step",
    ),
    [
        (
            "connectivity_monitor_zha",
            {
                CONF_PROTOCOL: PROTOCOL_ZHA,
                CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                "device_name": "Hallway Sensor",
            },
            "zha_alert_select",
            "ieee",
            "00:11:22:33:44:55:66:77",
            "zha_alert_config",
        ),
        (
            "connectivity_monitor_matter",
            {
                CONF_PROTOCOL: PROTOCOL_MATTER,
                CONF_HOST: "matter:1-1234",
                CONF_MATTER_NODE_ID: "1-1234",
                "device_name": "Thermostat",
            },
            "matter_alert_select",
            "node_id",
            "1-1234",
            "matter_alert_config",
        ),
        (
            "connectivity_monitor_esphome",
            {
                CONF_PROTOCOL: PROTOCOL_ESPHOME,
                CONF_HOST: "esphome:node-1",
                CONF_ESPHOME_DEVICE_ID: "node-1",
                "device_name": "Garage Node",
            },
            "esphome_alert_select",
            "device_id",
            "node-1",
            "esphome_alert_config",
        ),
        (
            "connectivity_monitor_bluetooth",
            {
                CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                CONF_HOST: "bluetooth:AA:BB:CC:DD:EE:FF",
                CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                "device_name": "Tracker",
            },
            "bluetooth_alert_select",
            "bt_address",
            "AA:BB:CC:DD:EE:FF",
            "bluetooth_alert_config",
        ),
    ],
)
async def test_options_flow_updates_protocol_specific_alert_settings(
    hass: HomeAssistant,
    entry_unique_id: str,
    target: dict[str, str],
    selection_step: str,
    selection_key: str,
    selection_value: str,
    config_step: str,
) -> None:
    """Test protocol-specific option flows update alert settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Typed Monitor",
        unique_id=entry_unique_id,
        version=2,
        data={
            CONF_TARGETS: [target],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)

    hass.states.async_set(
        "automation.device_recovery", "on", {"friendly_name": "Device Recovery"}
    )
    hass.services.async_register("notify", "mobile_app", lambda call: None)

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "alerts"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == selection_step

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={selection_key: selection_value}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == config_step

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_ALERTS_ENABLED: True,
                CONF_ALERT_GROUP: "mobile_app",
                CONF_ALERT_DELAY: 12,
                CONF_ALERT_ACTION_ENABLED: True,
                CONF_ALERT_ACTION: "automation.device_recovery",
                CONF_ALERT_ACTION_DELAY: 20,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert mock_reload.await_count == 1
    assert entry.data == {
        CONF_TARGETS: [
            {
                **target,
                CONF_ALERT_GROUP: "mobile_app",
                CONF_ALERT_DELAY: 12,
                CONF_ALERT_ACTION: "automation.device_recovery",
                CONF_ALERT_ACTION_DELAY: 20,
            }
        ],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


@pytest.mark.parametrize(
    (
        "entry_unique_id",
        "target",
        "remove_step",
        "selection_key",
        "selection_value",
        "entity_unique_id",
    ),
    [
        (
            "connectivity_monitor_zha",
            {
                CONF_PROTOCOL: PROTOCOL_ZHA,
                CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                "device_name": "Hallway Sensor",
            },
            "remove_zha_device",
            "ieee",
            "00:11:22:33:44:55:66:77",
            "connectivity_zha_0011223344556677",
        ),
        (
            "connectivity_monitor_matter",
            {
                CONF_PROTOCOL: PROTOCOL_MATTER,
                CONF_HOST: "matter:1-1234",
                CONF_MATTER_NODE_ID: "1-1234",
                "device_name": "Thermostat",
            },
            "remove_matter_device",
            "node_id",
            "1-1234",
            "connectivity_matter_1_1234",
        ),
        (
            "connectivity_monitor_esphome",
            {
                CONF_PROTOCOL: PROTOCOL_ESPHOME,
                CONF_HOST: "esphome:node-1",
                CONF_ESPHOME_DEVICE_ID: "node-1",
                "device_name": "Garage Node",
            },
            "remove_esphome_device",
            "device_id",
            "node-1",
            "connectivity_esphome_node_1",
        ),
        (
            "connectivity_monitor_bluetooth",
            {
                CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                CONF_HOST: "bluetooth:AA:BB:CC:DD:EE:FF",
                CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                "device_name": "Tracker",
            },
            "remove_bluetooth_device",
            "bt_address",
            "AA:BB:CC:DD:EE:FF",
            "connectivity_bluetooth_AA_BB_CC_DD_EE_FF",
        ),
    ],
)
async def test_options_flow_removes_protocol_specific_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entry_unique_id: str,
    target: dict[str, str],
    remove_step: str,
    selection_key: str,
    selection_value: str,
    entity_unique_id: str,
) -> None:
    """Test protocol-specific option flows remove monitored devices and entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Typed Monitor",
        unique_id=entry_unique_id,
        version=2,
        data={
            CONF_TARGETS: [target],
            CONF_INTERVAL: 30,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    entry.add_to_hass(hass)
    created_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        entity_unique_id,
        config_entry=entry,
        original_name=target["device_name"],
    )

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "remove_device"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == remove_step

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={selection_key: selection_value}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert mock_reload.await_count == 1
    assert entry.data == {
        CONF_TARGETS: [],
        CONF_INTERVAL: 30,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }
    assert entity_registry.async_get(created_entity.entity_id) is None


async def test_zha_flow_create_first_entry(hass: HomeAssistant) -> None:
    """Test creating the initial ZigBee Monitor entry via the ZHA flow."""
    with patch(
        "homeassistant.components.connectivity_monitor.config_flow.async_get_zha_devices",
        AsyncMock(
            return_value=[
                {
                    "ieee": "00:11:22:33:44:55:66:77",
                    "name": "Front Door Sensor",
                    "model": "Z-Sensor",
                    "manufacturer": "ZigBeeInc",
                }
            ]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "zha"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "zha_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "zha_configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_name": "Front Door Sensor",
                CONF_INACTIVE_TIMEOUT: DEFAULT_INACTIVE_TIMEOUT,
                CONF_ALERTS_ENABLED: False,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION_ENABLED: False,
                CONF_ALERT_ACTION_DELAY: 30,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "dns"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "interval"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_INTERVAL: 60}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ZigBee Monitor"
    assert result["result"].unique_id == "connectivity_monitor_zha"
    assert result["data"] == {
        CONF_TARGETS: [
            {
                CONF_PROTOCOL: PROTOCOL_ZHA,
                CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                "device_name": "Front Door Sensor",
                CONF_INACTIVE_TIMEOUT: DEFAULT_INACTIVE_TIMEOUT,
                CONF_ALERT_GROUP: None,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION: "",
                CONF_ALERT_ACTION_DELAY: 30,
                "model": "Z-Sensor",
                "manufacturer": "ZigBeeInc",
            }
        ],
        CONF_INTERVAL: 60,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_zha_flow_updates_existing_typed_entry(hass: HomeAssistant) -> None:
    """Test that adding a second ZHA device updates the existing ZigBee Monitor entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="ZigBee Monitor",
        unique_id="connectivity_monitor_zha",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_PROTOCOL: PROTOCOL_ZHA,
                    CONF_HOST: "zha:00:11:22:33:44:55:66:77",
                    CONF_ZHA_IEEE: "00:11:22:33:44:55:66:77",
                    "device_name": "Front Door Sensor",
                }
            ],
            CONF_INTERVAL: 60,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    existing_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.config_flow.async_get_zha_devices",
            AsyncMock(
                return_value=[
                    {
                        "ieee": "00:11:22:33:44:55:66:77",
                        "name": "Front Door Sensor",
                    },
                    {
                        "ieee": "AA:BB:CC:DD:EE:FF:00:11",
                        "name": "Motion Sensor",
                        "model": "PIR-100",
                        "manufacturer": "ZigBeeInc",
                    },
                ]
            ),
        ),
        patch.object(
            hass.config_entries, "async_reload", AsyncMock(return_value=True)
        ) as mock_reload,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "zha"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "zha_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ZHA_IEEE: "AA:BB:CC:DD:EE:FF:00:11"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "zha_configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_name": "Motion Sensor",
                CONF_INACTIVE_TIMEOUT: DEFAULT_INACTIVE_TIMEOUT,
                CONF_ALERTS_ENABLED: False,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION_ENABLED: False,
                CONF_ALERT_ACTION_DELAY: 30,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"
    assert mock_reload.await_count == 1
    assert len(existing_entry.data[CONF_TARGETS]) == 2
    new_target = existing_entry.data[CONF_TARGETS][1]
    assert new_target[CONF_ZHA_IEEE] == "AA:BB:CC:DD:EE:FF:00:11"
    assert new_target["device_name"] == "Motion Sensor"
    assert new_target["model"] == "PIR-100"
    assert new_target["manufacturer"] == "ZigBeeInc"


async def test_esphome_flow_create_first_entry(hass: HomeAssistant) -> None:
    """Test creating the initial ESPHome Monitor entry via the ESPHome flow."""
    with patch(
        "homeassistant.components.connectivity_monitor.config_flow.async_get_esphome_devices",
        AsyncMock(
            return_value=[
                {
                    "device_id": "node-garage",
                    "name": "Garage Node",
                    "model": "ESP32",
                    "manufacturer": "Espressif",
                    "esphome_identifier": "garage-node",
                    "esphome_mac": "AA:BB:CC:DD:EE:01",
                }
            ]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "esphome"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "esphome_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ESPHOME_DEVICE_ID: "node-garage"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "esphome_configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_name": "Garage Node",
                CONF_ALERTS_ENABLED: False,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION_ENABLED: False,
                CONF_ALERT_ACTION_DELAY: 30,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "dns"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "interval"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_INTERVAL: 60}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ESPHome Monitor"
    assert result["result"].unique_id == "connectivity_monitor_esphome"
    assert result["data"] == {
        CONF_TARGETS: [
            {
                CONF_PROTOCOL: PROTOCOL_ESPHOME,
                CONF_HOST: "esphome:node-garage",
                CONF_ESPHOME_DEVICE_ID: "node-garage",
                "esphome_identifier": "garage-node",
                "esphome_mac": "AA:BB:CC:DD:EE:01",
                "device_name": "Garage Node",
                CONF_ALERT_GROUP: None,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION: "",
                CONF_ALERT_ACTION_DELAY: 30,
                "model": "ESP32",
                "manufacturer": "Espressif",
            }
        ],
        CONF_INTERVAL: 60,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_esphome_flow_updates_existing_typed_entry(hass: HomeAssistant) -> None:
    """Test that adding a second ESPHome device updates the existing ESPHome Monitor entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="ESPHome Monitor",
        unique_id="connectivity_monitor_esphome",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_PROTOCOL: PROTOCOL_ESPHOME,
                    CONF_HOST: "esphome:node-garage",
                    CONF_ESPHOME_DEVICE_ID: "node-garage",
                    "device_name": "Garage Node",
                }
            ],
            CONF_INTERVAL: 60,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    existing_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.config_flow.async_get_esphome_devices",
            AsyncMock(
                return_value=[
                    {"device_id": "node-garage", "name": "Garage Node"},
                    {
                        "device_id": "node-kitchen",
                        "name": "Kitchen Node",
                        "model": "ESP8266",
                        "manufacturer": "Espressif",
                        "esphome_identifier": "kitchen-node",
                        "esphome_mac": "AA:BB:CC:DD:EE:02",
                    },
                ]
            ),
        ),
        patch.object(
            hass.config_entries, "async_reload", AsyncMock(return_value=True)
        ) as mock_reload,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "esphome"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "esphome_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ESPHOME_DEVICE_ID: "node-kitchen"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "esphome_configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_name": "Kitchen Node",
                CONF_ALERTS_ENABLED: False,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION_ENABLED: False,
                CONF_ALERT_ACTION_DELAY: 30,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"
    assert mock_reload.await_count == 1
    assert len(existing_entry.data[CONF_TARGETS]) == 2
    new_target = existing_entry.data[CONF_TARGETS][1]
    assert new_target[CONF_ESPHOME_DEVICE_ID] == "node-kitchen"
    assert new_target["device_name"] == "Kitchen Node"
    assert new_target["esphome_identifier"] == "kitchen-node"
    assert new_target["model"] == "ESP8266"


async def test_bluetooth_flow_create_first_entry(hass: HomeAssistant) -> None:
    """Test creating the initial Bluetooth Monitor entry via the Bluetooth flow."""
    with patch(
        "homeassistant.components.connectivity_monitor.config_flow.async_get_bluetooth_devices",
        AsyncMock(
            return_value=[
                {
                    "bt_address": "AA:BB:CC:DD:EE:FF",
                    "name": "Fitness Tracker",
                    "model": "FitBand 3",
                    "manufacturer": "FitCo",
                    "rssi": -65,
                }
            ]
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "bluetooth"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_name": "Fitness Tracker",
                CONF_ALERTS_ENABLED: False,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION_ENABLED: False,
                CONF_ALERT_ACTION_DELAY: 30,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "dns"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "interval"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_INTERVAL: 60}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bluetooth Monitor"
    assert result["result"].unique_id == "connectivity_monitor_bluetooth"
    assert result["data"] == {
        CONF_TARGETS: [
            {
                CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                CONF_HOST: "bluetooth:AA:BB:CC:DD:EE:FF",
                CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                "device_name": "Fitness Tracker",
                CONF_ALERT_GROUP: None,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION: "",
                CONF_ALERT_ACTION_DELAY: 30,
                "model": "FitBand 3",
                "manufacturer": "FitCo",
            }
        ],
        CONF_INTERVAL: 60,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }


async def test_bluetooth_flow_updates_existing_typed_entry(
    hass: HomeAssistant,
) -> None:
    """Test that adding a second Bluetooth device updates the existing Bluetooth Monitor entry."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bluetooth Monitor",
        unique_id="connectivity_monitor_bluetooth",
        version=2,
        data={
            CONF_TARGETS: [
                {
                    CONF_PROTOCOL: PROTOCOL_BLUETOOTH,
                    CONF_HOST: "bluetooth:AA:BB:CC:DD:EE:FF",
                    CONF_BLUETOOTH_ADDRESS: "AA:BB:CC:DD:EE:FF",
                    "device_name": "Fitness Tracker",
                }
            ],
            CONF_INTERVAL: 60,
            CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
        },
    )
    existing_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.connectivity_monitor.config_flow.async_get_bluetooth_devices",
            AsyncMock(
                return_value=[
                    {"bt_address": "AA:BB:CC:DD:EE:FF", "name": "Fitness Tracker"},
                    {
                        "bt_address": "11:22:33:44:55:66",
                        "name": "Smart Lock",
                        "model": "Lock Pro",
                        "manufacturer": "LockCo",
                        "rssi": -50,
                    },
                ]
            ),
        ),
        patch.object(
            hass.config_entries, "async_reload", AsyncMock(return_value=True)
        ) as mock_reload,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device_type": "bluetooth"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BLUETOOTH_ADDRESS: "11:22:33:44:55:66"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device_name": "Smart Lock",
                CONF_ALERTS_ENABLED: False,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION_ENABLED: False,
                CONF_ALERT_ACTION_DELAY: 30,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "device_added"
    assert mock_reload.await_count == 1
    assert len(existing_entry.data[CONF_TARGETS]) == 2
    new_target = existing_entry.data[CONF_TARGETS][1]
    assert new_target[CONF_BLUETOOTH_ADDRESS] == "11:22:33:44:55:66"
    assert new_target["device_name"] == "Smart Lock"
    assert new_target["model"] == "Lock Pro"
    assert new_target["manufacturer"] == "LockCo"


async def test_network_flow_udp_includes_port_step(hass: HomeAssistant) -> None:
    """Test creating a UDP target goes through the port step and produces a correct entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device_type": "network"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.5",
            CONF_PROTOCOL: PROTOCOL_UDP,
            "device_name": "NTP Server",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "port"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"port": 123}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dns"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DNS_SERVER: DEFAULT_DNS_SERVER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "interval"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Network Monitor"
    assert result["result"].unique_id == "connectivity_monitor_network"
    assert result["data"] == {
        CONF_TARGETS: [
            {
                CONF_HOST: "10.0.0.5",
                CONF_PROTOCOL: PROTOCOL_UDP,
                "device_name": "NTP Server",
                CONF_ALERT_GROUP: None,
                CONF_ALERT_DELAY: 15,
                CONF_ALERT_ACTION: "",
                CONF_ALERT_ACTION_DELAY: 30,
                "port": 123,
            }
        ],
        CONF_INTERVAL: 60,
        CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    }
