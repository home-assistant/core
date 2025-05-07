"""Test the Z-Wave JS Websocket API."""

from copy import deepcopy
from http import HTTPStatus
from io import BytesIO
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

import pytest
from zwave_js_server.const import (
    ExclusionStrategy,
    InclusionState,
    InclusionStrategy,
    LogLevel,
    Protocols,
    ProvisioningEntryStatus,
    QRCodeVersion,
    SecurityClass,
    ZwaveFeature,
)
from zwave_js_server.event import Event
from zwave_js_server.exceptions import (
    FailedCommand,
    FailedZWaveCommand,
    InvalidNewValue,
    NotFoundError,
    SetValueFailed,
)
from zwave_js_server.model.controller import (
    ProvisioningEntry,
    QRProvisioningInformation,
)
from zwave_js_server.model.controller.firmware import ControllerFirmwareUpdateData
from zwave_js_server.model.node import Node
from zwave_js_server.model.node.firmware import NodeFirmwareUpdateData
from zwave_js_server.model.value import ConfigurationValue, get_value_id_str

from homeassistant.components.websocket_api import ERR_INVALID_FORMAT, ERR_NOT_FOUND
from homeassistant.components.zwave_js.api import (
    APPLICATION_VERSION,
    AREA_ID,
    CLIENT_SIDE_AUTH,
    COMMAND_CLASS_ID,
    CONFIG,
    DEVICE_ID,
    DEVICE_NAME,
    DSK,
    ENABLED,
    ENDPOINT,
    ENTRY_ID,
    ERR_NOT_LOADED,
    FEATURE,
    FILENAME,
    FORCE_CONSOLE,
    GENERIC_DEVICE_CLASS,
    ID,
    INCLUSION_STRATEGY,
    INSTALLER_ICON_TYPE,
    LEVEL,
    LOG_TO_FILE,
    MANUFACTURER_ID,
    MAX_INCLUSION_REQUEST_INTERVAL,
    NODE_ID,
    OPTED_IN,
    PIN,
    PLANNED_PROVISIONING_ENTRY,
    PRODUCT_ID,
    PRODUCT_TYPE,
    PROPERTY,
    PROPERTY_KEY,
    PROTOCOL,
    QR_CODE_STRING,
    QR_PROVISIONING_INFORMATION,
    REQUESTED_SECURITY_CLASSES,
    SECURITY_CLASSES,
    SPECIFIC_DEVICE_CLASS,
    STATUS,
    STRATEGY,
    SUPPORTED_PROTOCOLS,
    TYPE,
    UUID,
    VALUE,
    VALUE_FORMAT,
    VALUE_SIZE,
    VERSION,
)
from homeassistant.components.zwave_js.const import (
    ATTR_COMMAND_CLASS,
    ATTR_ENDPOINT,
    ATTR_METHOD_NAME,
    ATTR_PARAMETERS,
    ATTR_WAIT_FOR_RESULT,
    CONF_DATA_COLLECTION_OPTED_IN,
    CONF_INSTALLER_MODE,
    DOMAIN,
)
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockUser
from tests.typing import ClientSessionGenerator, WebSocketGenerator

CONTROLLER_PATCH_PREFIX = "zwave_js_server.model.controller.Controller"


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return []


def get_device(hass: HomeAssistant, node):
    """Get device ID for a node."""
    dev_reg = dr.async_get(hass)
    device_id = get_device_id(node.client.driver, node)
    return dev_reg.async_get_device(identifiers={device_id})


async def test_no_driver(
    hass: HomeAssistant,
    client,
    multisensor_6,
    controller_state,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test driver missing results in error."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    client.driver = None

    # Try API call with entry ID
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/network_status",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]


async def test_network_status(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6,
    controller_state,
    client,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the network status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    client.server_logging_enabled = False

    # Try API call with entry ID
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_state",
        return_value=controller_state["controller"],
    ):
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "zwave_js/network_status",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]

    assert result["client"]["ws_server_url"] == "ws://test:3000/zjs"
    assert result["client"]["server_version"] == "1.0.0"
    assert not result["client"]["server_logging_enabled"]
    assert result["controller"]["inclusion_state"] == InclusionState.IDLE
    assert result["controller"]["supports_long_range"]

    # Try API call with device ID
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "3245146787-52")},
    )
    assert device
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_state",
        return_value=controller_state["controller"],
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/network_status",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()
        result = msg["result"]

    assert result["client"]["ws_server_url"] == "ws://test:3000/zjs"
    assert result["client"]["server_version"] == "1.0.0"
    assert result["controller"]["inclusion_state"] == InclusionState.IDLE

    # Test sending command with invalid config entry ID fails
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/network_status",
            ENTRY_ID: "fake_id",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with invalid device ID fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/network_status",
            DEVICE_ID: "fake_id",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails with config entry ID
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/network_status",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    # Test sending command with not loaded entry fails with device ID
    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/network_status",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    # Test sending command with no device ID or entry ID fails
    await ws_client.send_json(
        {
            ID: 7,
            TYPE: "zwave_js/network_status",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_INVALID_FORMAT


async def test_subscribe_node_status(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6_state,
    client,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the subscribe node status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    node_data = deepcopy(multisensor_6_state)  # Copy to allow modification in tests.
    node = Node(client, node_data)
    node.data["ready"] = False
    driver = client.driver
    driver.controller.nodes[node.node_id] = node

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={get_device_id(driver, node)}
    )

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_node_status",
            DEVICE_ID: device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    new_node_data = deepcopy(multisensor_6_state)
    new_node_data["ready"] = True

    event = Event(
        "ready",
        {
            "source": "node",
            "event": "ready",
            "nodeId": node.node_id,
            "nodeState": new_node_data,
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    msg = await ws_client.receive_json()

    assert msg["event"]["event"] == "ready"
    assert msg["event"]["status"] == 1
    assert msg["event"]["ready"]

    event = Event(
        "wake up",
        {
            "source": "node",
            "event": "wake up",
            "nodeId": node.node_id,
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    msg = await ws_client.receive_json()

    assert msg["event"]["event"] == "wake up"
    assert msg["event"]["status"] == 2
    assert msg["event"]["ready"]


async def test_node_status(
    hass: HomeAssistant, multisensor_6, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the node status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    node = multisensor_6
    device = get_device(hass, node)
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/node_status",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result[NODE_ID] == 52
    assert result["ready"]
    assert result["is_routing"]
    assert not result["is_secure"]
    assert result["status"] == 1
    assert result["zwave_plus_version"] == 1
    assert result["highest_security_class"] == SecurityClass.S0_LEGACY
    assert not result["is_controller_node"]
    assert not result["has_firmware_update_cc"]

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/node_status",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/node_status",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_node_metadata(
    hass: HomeAssistant,
    wallmote_central_scene,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the node metadata websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    node = wallmote_central_scene
    device = get_device(hass, node)
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/node_metadata",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result[NODE_ID] == 35
    assert result["inclusion"] == (
        "To add the ZP3111 to the Z-Wave network (inclusion), place the Z-Wave "
        "primary controller into inclusion mode. Press the Program Switch of ZP3111 "
        "for sending the NIF. After sending NIF, Z-Wave will send the auto inclusion, "
        "otherwise, ZP3111 will go to sleep after 20 seconds."
    )
    assert result["exclusion"] == (
        "To remove the ZP3111 from the Z-Wave network (exclusion), place the Z-Wave "
        "primary controller into \u201cexclusion\u201d mode, and following its "
        "instruction to delete the ZP3111 to the controller. Press the Program Switch "
        "of ZP3111 once to be excluded."
    )
    assert result["reset"] == (
        "Remove cover to triggered tamper switch, LED flash once & send out Alarm "
        "Report. Press Program Switch 10 times within 10 seconds, ZP3111 will send "
        "the \u201cDevice Reset Locally Notification\u201d command and reset to the "
        "factory default. (Remark: This is to be used only in the case of primary "
        "controller being inoperable or otherwise unavailable.)"
    )
    assert result["manual"] == (
        "https://products.z-wavealliance.org/ProductManual/File?folder=&filename="
        "MarketCertificationFiles/2479/ZP3111-5_R2_20170316.pdf"
    )
    assert not result["wakeup"]
    assert (
        result["device_database_url"]
        == "https://devices.zwave-js.io/?jumpTo=0x0086:0x0002:0x0082:0.0"
    )

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/node_metadata",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/node_metadata",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_node_alerts(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    wallmote_central_scene,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the node comments websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "3245146787-35")})
    assert device

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/node_alerts",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result["comments"] == [{"level": "info", "text": "test"}]
    assert result["is_embedded"]

    # Test with provisioned device
    valid_qr_info = {
        VERSION: 1,
        SECURITY_CLASSES: [0],
        DSK: "test",
        GENERIC_DEVICE_CLASS: 1,
        SPECIFIC_DEVICE_CLASS: 1,
        INSTALLER_ICON_TYPE: 1,
        MANUFACTURER_ID: 1,
        PRODUCT_TYPE: 1,
        PRODUCT_ID: 1,
        APPLICATION_VERSION: "test",
    }

    # Test QR provisioning information
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/provision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            QR_PROVISIONING_INFORMATION: valid_qr_info,
            DEVICE_NAME: "test",
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entries",
        return_value=[
            ProvisioningEntry.from_dict({**valid_qr_info, "device_id": msg["result"]})
        ],
    ):
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/node_alerts",
                DEVICE_ID: msg["result"],
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]
        assert msg["result"]["comments"] == [
            {
                "level": "info",
                "text": "This device has been provisioned but is not yet included in the network.",
            }
        ]

    # Test missing node with no provisioning entry
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-12")},
    )
    assert device
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/node_alerts",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test integration not loaded error - need to unload the integration
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/node_alerts",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_add_node(
    hass: HomeAssistant,
    nortek_thermostat,
    nortek_thermostat_added_event,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the add_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    # Test inclusion with no provisioning input
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.DEFAULT.value,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {"strategy": InclusionStrategy.DEFAULT},
    }

    event = Event(
        type="inclusion started",
        data={
            "source": "controller",
            "event": "inclusion started",
            "strategy": 2,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "inclusion started"

    event = Event(
        type="node found",
        data={
            "source": "controller",
            "event": "node found",
            "node": {
                "nodeId": 67,
            },
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node found"
    node_details = {
        "node_id": 67,
    }
    assert msg["event"]["node"] == node_details

    event = Event(
        type="grant security classes",
        data={
            "source": "controller",
            "event": "grant security classes",
            "requested": {"securityClasses": [0, 1, 2, 7], "clientSideAuth": False},
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "grant security classes"
    assert msg["event"]["requested_grant"] == {
        "securityClasses": [0, 1, 2, 7],
        "clientSideAuth": False,
    }

    event = Event(
        type="validate dsk and enter pin",
        data={
            "source": "controller",
            "event": "validate dsk and enter pin",
            "dsk": "test",
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "validate dsk and enter pin"
    assert msg["event"]["dsk"] == "test"

    client.driver.receive_event(nortek_thermostat_added_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node added"
    node_details = {
        "node_id": 67,
        "status": 0,
        "ready": False,
        "low_security": False,
        "low_security_reason": None,
    }
    assert msg["event"]["node"] == node_details

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "device registered"
    # Check the keys of the device item
    assert list(msg["event"]["device"]) == ["name", "id", "manufacturer", "model"]

    # Test receiving interview events
    event = Event(
        type="interview started",
        data={"source": "node", "event": "interview started", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview started"

    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": 67,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview stage completed"
    assert msg["event"]["stage"] == "NodeInfo"

    event = Event(
        type="interview completed",
        data={"source": "node", "event": "interview completed", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview completed"

    event = Event(
        type="interview failed",
        data={
            "source": "node",
            "event": "interview failed",
            "nodeId": 67,
            "args": {
                "errorMessage": "error",
                "isFinal": True,
            },
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview failed"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 planned provisioning entry
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            PLANNED_PROVISIONING_ENTRY: {
                DSK: "test",
                SECURITY_CLASSES: [0],
            },
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "provisioning": ProvisioningEntry(
                "test", [SecurityClass.S2_UNAUTHENTICATED]
            ).to_dict(),
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 QR provisioning information
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            QR_PROVISIONING_INFORMATION: {
                VERSION: 0,
                SECURITY_CLASSES: [0],
                DSK: "test",
                GENERIC_DEVICE_CLASS: 1,
                SPECIFIC_DEVICE_CLASS: 1,
                INSTALLER_ICON_TYPE: 1,
                MANUFACTURER_ID: 1,
                PRODUCT_TYPE: 1,
                PRODUCT_ID: 1,
                APPLICATION_VERSION: "test",
            },
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "provisioning": QRProvisioningInformation(
                version=QRCodeVersion.S2,
                security_classes=[SecurityClass.S2_UNAUTHENTICATED],
                dsk="test",
                generic_device_class=1,
                specific_device_class=1,
                installer_icon_type=1,
                manufacturer_id=1,
                product_type=1,
                product_id=1,
                application_version="test",
                max_inclusion_request_interval=None,
                uuid=None,
                supported_protocols=None,
            ).to_dict(),
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 QR provisioning information
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            QR_PROVISIONING_INFORMATION: {
                VERSION: 0,
                SECURITY_CLASSES: [0],
                DSK: "test",
                GENERIC_DEVICE_CLASS: 1,
                SPECIFIC_DEVICE_CLASS: 1,
                INSTALLER_ICON_TYPE: 1,
                MANUFACTURER_ID: 1,
                PRODUCT_TYPE: 1,
                PRODUCT_ID: 1,
                APPLICATION_VERSION: "test",
                STATUS: 1,
                REQUESTED_SECURITY_CLASSES: [0],
            },
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "provisioning": QRProvisioningInformation(
                version=QRCodeVersion.S2,
                security_classes=[SecurityClass.S2_UNAUTHENTICATED],
                dsk="test",
                generic_device_class=1,
                specific_device_class=1,
                installer_icon_type=1,
                manufacturer_id=1,
                product_type=1,
                product_id=1,
                application_version="test",
                max_inclusion_request_interval=None,
                uuid=None,
                supported_protocols=None,
                status=ProvisioningEntryStatus.INACTIVE,
                requested_security_classes=[SecurityClass.S2_UNAUTHENTICATED],
            ).to_dict(),
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 QR code string
    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "provisioning": "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 DSK string string
    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            DSK: "test_dsk",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_inclusion",
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "dsk": "test_dsk",
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test Smart Start QR provisioning information with S2 inclusion strategy fails
    await ws_client.send_json(
        {
            ID: 7,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            QR_PROVISIONING_INFORMATION: {
                VERSION: 1,
                SECURITY_CLASSES: [0],
                DSK: "test",
                GENERIC_DEVICE_CLASS: 1,
                SPECIFIC_DEVICE_CLASS: 1,
                INSTALLER_ICON_TYPE: 1,
                MANUFACTURER_ID: 1,
                PRODUCT_TYPE: 1,
                PRODUCT_ID: 1,
                APPLICATION_VERSION: "test",
            },
        }
    )

    msg = await ws_client.receive_json()
    assert not msg["success"]

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test QR provisioning information with S0 inclusion strategy fails
    await ws_client.send_json(
        {
            ID: 8,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S0,
            QR_PROVISIONING_INFORMATION: {
                VERSION: 1,
                SECURITY_CLASSES: [0],
                DSK: "test",
                GENERIC_DEVICE_CLASS: 1,
                SPECIFIC_DEVICE_CLASS: 1,
                INSTALLER_ICON_TYPE: 1,
                MANUFACTURER_ID: 1,
                PRODUCT_TYPE: 1,
                PRODUCT_ID: 1,
                APPLICATION_VERSION: "test",
            },
        }
    )

    msg = await ws_client.receive_json()
    assert not msg["success"]

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {" success": True}

    # Test ValueError is caught as failure
    await ws_client.send_json(
        {
            ID: 9,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.DEFAULT.value,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )

    msg = await ws_client.receive_json()
    assert not msg["success"]

    assert len(client.async_send_command.call_args_list) == 0

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_begin_inclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 10,
                TYPE: "zwave_js/add_node",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test inclusion already in progress
    client.async_send_command.reset_mock()
    type(client.driver.controller).inclusion_state = PropertyMock(
        return_value=InclusionState.INCLUDING
    )

    # Create a node that's not ready
    node_data = deepcopy(nortek_thermostat.data)  # Copy to allow modification in tests.
    node_data["ready"] = False
    node_data["values"] = {}
    node_data["endpoints"] = {}
    node = Node(client, node_data)
    client.driver.controller.nodes[node.node_id] = node

    await ws_client.send_json(
        {
            ID: 11,
            TYPE: "zwave_js/add_node",
            ENTRY_ID: entry.entry_id,
            INCLUSION_STRATEGY: InclusionStrategy.DEFAULT.value,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    # Verify no command was sent since inclusion is already in progress
    assert len(client.async_send_command.call_args_list) == 0

    # Verify we got a node added event
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node added"
    assert msg["event"]["node"]["node_id"] == node.node_id

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 12, TYPE: "zwave_js/add_node", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_grant_security_classes(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the grant_security_classes websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/grant_security_classes",
            ENTRY_ID: entry.entry_id,
            SECURITY_CLASSES: [SecurityClass.S2_UNAUTHENTICATED],
            CLIENT_SIDE_AUTH: False,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.grant_security_classes",
        "inclusionGrant": {"securityClasses": [0], "clientSideAuth": False},
    }

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/grant_security_classes",
            ENTRY_ID: entry.entry_id,
            SECURITY_CLASSES: [SecurityClass.S2_UNAUTHENTICATED],
            CLIENT_SIDE_AUTH: False,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_validate_dsk_and_enter_pin(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the validate_dsk_and_enter_pin websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/validate_dsk_and_enter_pin",
            ENTRY_ID: entry.entry_id,
            PIN: "test",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.validate_dsk_and_enter_pin",
        "pin": "test",
    }

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/validate_dsk_and_enter_pin",
            ENTRY_ID: entry.entry_id,
            PIN: "test",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_provision_smart_start_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test provision_smart_start_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    valid_qr_info = {
        VERSION: 1,
        SECURITY_CLASSES: [0],
        DSK: "test",
        GENERIC_DEVICE_CLASS: 1,
        SPECIFIC_DEVICE_CLASS: 1,
        INSTALLER_ICON_TYPE: 1,
        MANUFACTURER_ID: 1,
        PRODUCT_TYPE: 1,
        PRODUCT_ID: 1,
        APPLICATION_VERSION: "test",
        "name": "test",
    }

    # Test QR provisioning information
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/provision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            QR_PROVISIONING_INFORMATION: valid_qr_info,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.provision_smart_start_node",
        "entry": ProvisioningEntry(
            dsk="test",
            security_classes=[SecurityClass.S2_UNAUTHENTICATED],
            additional_properties={"name": "test"},
        ).to_dict(),
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test QR provisioning information with device name and area
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/provision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            QR_PROVISIONING_INFORMATION: {
                **valid_qr_info,
            },
            PROTOCOL: Protocols.ZWAVE_LONG_RANGE,
            DEVICE_NAME: "test_name",
            AREA_ID: "test_area",
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    # verify a device was created
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "provision_test")},
    )
    assert device is not None
    assert device.name == "test_name"
    assert device.area_id == "test_area"

    assert len(client.async_send_command.call_args_list) == 2
    assert client.async_send_command.call_args_list[0][0][0] == {
        "command": "config_manager.lookup_device",
        "manufacturerId": 1,
        "productType": 1,
        "productId": 1,
    }
    assert client.async_send_command.call_args_list[1][0][0] == {
        "command": "controller.provision_smart_start_node",
        "entry": ProvisioningEntry(
            dsk="test",
            security_classes=[SecurityClass.S2_UNAUTHENTICATED],
            protocol=Protocols.ZWAVE_LONG_RANGE,
            additional_properties={
                "name": "test",
                "device_id": device.id,
            },
        ).to_dict(),
    }

    # Test QR provisioning information with S2 version throws error
    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/provision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            QR_PROVISIONING_INFORMATION: {
                VERSION: 0,
                SECURITY_CLASSES: [0],
                DSK: "test",
                GENERIC_DEVICE_CLASS: 1,
                SPECIFIC_DEVICE_CLASS: 1,
                INSTALLER_ICON_TYPE: 1,
                MANUFACTURER_ID: 1,
                PRODUCT_TYPE: 1,
                PRODUCT_ID: 1,
                APPLICATION_VERSION: "test",
            },
        }
    )

    msg = await ws_client.receive_json()
    assert not msg["success"]

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}
    assert len(client.async_send_command.call_args_list) == 0

    # Test no provisioning parameter provided causes failure
    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/provision_smart_start_node",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_provision_smart_start_node",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 7,
                TYPE: "zwave_js/provision_smart_start_node",
                ENTRY_ID: entry.entry_id,
                QR_PROVISIONING_INFORMATION: valid_qr_info,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 8,
            TYPE: "zwave_js/provision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            QR_PROVISIONING_INFORMATION: valid_qr_info,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_unprovision_smart_start_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test unprovision_smart_start_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {}

    # Test node ID as input
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/unprovision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            NODE_ID: 1,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 2
    assert client.async_send_command.call_args_list[0][0][0] == {
        "command": "controller.get_provisioning_entry",
        "dskOrNodeId": 1,
    }
    assert client.async_send_command.call_args_list[1][0][0] == {
        "command": "controller.unprovision_smart_start_node",
        "dskOrNodeId": 1,
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {}

    # Test DSK as input
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/unprovision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            DSK: "test",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 2
    assert client.async_send_command.call_args_list[0][0][0] == {
        "command": "controller.get_provisioning_entry",
        "dskOrNodeId": "test",
    }
    assert client.async_send_command.call_args_list[1][0][0] == {
        "command": "controller.unprovision_smart_start_node",
        "dskOrNodeId": "test",
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {}

    # Test not including DSK or node ID as input fails
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/unprovision_smart_start_node",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert not msg["success"]

    assert len(client.async_send_command.call_args_list) == 0

    # Test with pre provisioned device
    # Create device registry entry for mock node
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "provision_test"), ("other_domain", "test")},
        name="Node 67",
    )
    provisioning_entry = ProvisioningEntry.from_dict(
        {
            "dsk": "test",
            "securityClasses": [SecurityClass.S2_UNAUTHENTICATED],
            "device_id": device.id,
        }
    )
    with patch.object(
        client.driver.controller,
        "async_get_provisioning_entry",
        return_value=provisioning_entry,
    ):
        # Don't remove the device if it has additional identifiers
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/unprovision_smart_start_node",
                ENTRY_ID: entry.entry_id,
                DSK: "test",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        assert len(client.async_send_command.call_args_list) == 1
        assert client.async_send_command.call_args[0][0] == {
            "command": "controller.unprovision_smart_start_node",
            "dskOrNodeId": "test",
        }

        device = device_registry.async_get(device.id)
        assert device is not None

        client.async_send_command.reset_mock()

        # Remove the device if it doesn't have additional identifiers
        device_registry.async_update_device(
            device.id, new_identifiers={(DOMAIN, "provision_test")}
        )
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/unprovision_smart_start_node",
                ENTRY_ID: entry.entry_id,
                DSK: "test",
            }
        )
        msg = await ws_client.receive_json()
        assert msg["success"]

        assert len(client.async_send_command.call_args_list) == 1
        assert client.async_send_command.call_args[0][0] == {
            "command": "controller.unprovision_smart_start_node",
            "dskOrNodeId": "test",
        }

        # Verify device was removed from device registry
        device = device_registry.async_get(device.id)
        assert device is None

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_unprovision_smart_start_node",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/unprovision_smart_start_node",
                ENTRY_ID: entry.entry_id,
                DSK: "test",
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/unprovision_smart_start_node",
            ENTRY_ID: entry.entry_id,
            DSK: "test",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_get_provisioning_entries(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test get_provisioning_entries websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {
        "entries": [{"dsk": "test", "securityClasses": [0], "fake": "test"}]
    }

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/get_provisioning_entries",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == [
        {DSK: "test", SECURITY_CLASSES: [0], STATUS: 0, "fake": "test"}
    ]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.get_provisioning_entries",
    }

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entries",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 6,
                TYPE: "zwave_js/get_provisioning_entries",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 7, TYPE: "zwave_js/get_provisioning_entries", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_parse_qr_code_string(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test parse_qr_code_string websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {
        "qrProvisioningInformation": {
            "version": 0,
            "securityClasses": [0],
            "dsk": "test",
            "genericDeviceClass": 1,
            "specificDeviceClass": 1,
            "installerIconType": 1,
            "manufacturerId": 1,
            "productType": 1,
            "productId": 1,
            "applicationVersion": "test",
            "maxInclusionRequestInterval": 1,
            "uuid": "test",
            "supportedProtocols": [0],
        }
    }

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/parse_qr_code_string",
            ENTRY_ID: entry.entry_id,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        VERSION: 0,
        SECURITY_CLASSES: [0],
        DSK: "test",
        GENERIC_DEVICE_CLASS: 1,
        SPECIFIC_DEVICE_CLASS: 1,
        INSTALLER_ICON_TYPE: 1,
        MANUFACTURER_ID: 1,
        PRODUCT_TYPE: 1,
        PRODUCT_ID: 1,
        APPLICATION_VERSION: "test",
        MAX_INCLUSION_REQUEST_INTERVAL: 1,
        UUID: "test",
        SUPPORTED_PROTOCOLS: [Protocols.ZWAVE],
        STATUS: 0,
    }

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "utils.parse_qr_code_string",
        "qr": "90testtesttesttesttesttesttesttesttesttesttesttesttest",
    }

    # Test FailedZWaveCommand is caught
    with patch(
        "homeassistant.components.zwave_js.api.async_parse_qr_code_string",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 6,
                TYPE: "zwave_js/parse_qr_code_string",
                ENTRY_ID: entry.entry_id,
                QR_CODE_STRING: (
                    "90testtesttesttesttesttesttesttesttesttesttesttesttest"
                ),
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 7,
            TYPE: "zwave_js/parse_qr_code_string",
            ENTRY_ID: entry.entry_id,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_try_parse_dsk_from_qr_code_string(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test try_parse_dsk_from_qr_code_string websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"dsk": "a"}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/try_parse_dsk_from_qr_code_string",
            ENTRY_ID: entry.entry_id,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == "a"

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "utils.try_parse_dsk_from_qr_code_string",
        "qr": "90testtesttesttesttesttesttesttesttesttesttesttesttest",
    }

    # Test FailedZWaveCommand is caught
    with patch(
        "homeassistant.components.zwave_js.api.async_try_parse_dsk_from_qr_code_string",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 6,
                TYPE: "zwave_js/try_parse_dsk_from_qr_code_string",
                ENTRY_ID: entry.entry_id,
                QR_CODE_STRING: (
                    "90testtesttesttesttesttesttesttesttesttesttesttesttest"
                ),
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 7,
            TYPE: "zwave_js/try_parse_dsk_from_qr_code_string",
            ENTRY_ID: entry.entry_id,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_supports_feature(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test supports_feature websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"supported": True}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/supports_feature",
            ENTRY_ID: entry.entry_id,
            FEATURE: ZwaveFeature.SMART_START,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"supported": True}


async def test_cancel_inclusion_exclusion(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test cancelling the inclusion and exclusion process."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 4, TYPE: "zwave_js/stop_inclusion", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    await ws_client.send_json(
        {ID: 5, TYPE: "zwave_js/stop_exclusion", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_stop_inclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 6,
                TYPE: "zwave_js/stop_inclusion",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_stop_exclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 7,
                TYPE: "zwave_js/stop_exclusion",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 8, TYPE: "zwave_js/stop_inclusion", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {ID: 9, TYPE: "zwave_js/stop_exclusion", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_remove_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
    nortek_thermostat,
    nortek_thermostat_removed_event,
) -> None:
    """Test the remove_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 1, TYPE: "zwave_js/remove_node", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_exclusion",
    }

    event = Event(
        type="exclusion started",
        data={
            "source": "controller",
            "event": "exclusion started",
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "exclusion started"

    # Create device registry entry for mock node
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-67")},
        name="Node 67",
    )

    # Fire node removed event
    client.driver.receive_event(nortek_thermostat_removed_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node removed"

    # Verify device was removed from device registry
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "3245146787-67")},
    )
    assert device is None

    # Test unprovision parameter
    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/remove_node",
            ENTRY_ID: entry.entry_id,
            STRATEGY: ExclusionStrategy.EXCLUDE_ONLY,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.begin_exclusion",
        "options": {"strategy": 0},
    }

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_begin_exclusion",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/remove_node",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 5, TYPE: "zwave_js/remove_node", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_replace_failed_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    nortek_thermostat,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
    nortek_thermostat_added_event,
    nortek_thermostat_removed_event,
) -> None:
    """Test the replace_failed_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Create device registry entry for mock node
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-67")},
        name="Node 67",
    )

    client.async_send_command.return_value = {"success": True}

    # Test replace failed node with no provisioning information
    # Order of events we receive for a successful replacement is `inclusion started`,
    # `inclusion stopped`, `node removed`, `node added`, then interview stages.
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/replace_failed_node",
            DEVICE_ID: device.id,
            INCLUSION_STRATEGY: InclusionStrategy.DEFAULT.value,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.replace_failed_node",
        "nodeId": nortek_thermostat.node_id,
        "options": {"strategy": InclusionStrategy.DEFAULT},
    }

    client.async_send_command.reset_mock()

    event = Event(
        type="inclusion started",
        data={
            "source": "controller",
            "event": "inclusion started",
            "strategy": 2,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "inclusion started"

    event = Event(
        type="node found",
        data={
            "source": "controller",
            "event": "node found",
            "node": {
                "nodeId": 67,
            },
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node found"
    node_details = {
        "node_id": 67,
    }
    assert msg["event"]["node"] == node_details

    event = Event(
        type="grant security classes",
        data={
            "source": "controller",
            "event": "grant security classes",
            "requested": {"securityClasses": [0, 1, 2, 7], "clientSideAuth": False},
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "grant security classes"
    assert msg["event"]["requested_grant"] == {
        "securityClasses": [0, 1, 2, 7],
        "clientSideAuth": False,
    }

    event = Event(
        type="validate dsk and enter pin",
        data={
            "source": "controller",
            "event": "validate dsk and enter pin",
            "dsk": "test",
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "validate dsk and enter pin"
    assert msg["event"]["dsk"] == "test"

    event = Event(
        type="inclusion stopped",
        data={
            "source": "controller",
            "event": "inclusion stopped",
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "inclusion stopped"

    # Fire node removed event
    client.driver.receive_event(nortek_thermostat_removed_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node removed"

    # Verify device was removed from device registry
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, "3245146787-67")},
        )
        is None
    )

    client.driver.receive_event(nortek_thermostat_added_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node added"
    node_details = {
        "node_id": 67,
        "status": 0,
        "ready": False,
    }
    assert msg["event"]["node"] == node_details

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "device registered"
    # Check the keys of the device item
    assert list(msg["event"]["device"]) == ["name", "id", "manufacturer", "model"]

    # Test receiving interview events
    event = Event(
        type="interview started",
        data={"source": "node", "event": "interview started", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview started"

    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": 67,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview stage completed"
    assert msg["event"]["stage"] == "NodeInfo"

    event = Event(
        type="interview completed",
        data={"source": "node", "event": "interview completed", "nodeId": 67},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview completed"

    event = Event(
        type="interview failed",
        data={
            "source": "node",
            "event": "interview failed",
            "nodeId": 67,
            "args": {
                "errorMessage": "error",
                "isFinal": True,
            },
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview failed"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 planned provisioning entry
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/replace_failed_node",
            DEVICE_ID: device.id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            PLANNED_PROVISIONING_ENTRY: {
                DSK: "test",
                SECURITY_CLASSES: [0],
            },
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.replace_failed_node",
        "nodeId": 67,
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "provisioning": ProvisioningEntry(
                "test", [SecurityClass.S2_UNAUTHENTICATED]
            ).to_dict(),
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 QR provisioning information
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/replace_failed_node",
            DEVICE_ID: device.id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            QR_PROVISIONING_INFORMATION: {
                VERSION: 0,
                SECURITY_CLASSES: [0],
                DSK: "test",
                GENERIC_DEVICE_CLASS: 1,
                SPECIFIC_DEVICE_CLASS: 1,
                INSTALLER_ICON_TYPE: 1,
                MANUFACTURER_ID: 1,
                PRODUCT_TYPE: 1,
                PRODUCT_ID: 1,
                APPLICATION_VERSION: "test",
            },
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.replace_failed_node",
        "nodeId": 67,
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "provisioning": QRProvisioningInformation(
                version=QRCodeVersion.S2,
                security_classes=[SecurityClass.S2_UNAUTHENTICATED],
                dsk="test",
                generic_device_class=1,
                specific_device_class=1,
                installer_icon_type=1,
                manufacturer_id=1,
                product_type=1,
                product_id=1,
                application_version="test",
                max_inclusion_request_interval=None,
                uuid=None,
                supported_protocols=None,
            ).to_dict(),
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test S2 QR code string
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/replace_failed_node",
            DEVICE_ID: device.id,
            INCLUSION_STRATEGY: InclusionStrategy.SECURITY_S2.value,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "controller.replace_failed_node",
        "nodeId": 67,
        "options": {
            "strategy": InclusionStrategy.SECURITY_S2,
            "provisioning": "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        },
    }

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"success": True}

    # Test ValueError is caught as failure
    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/replace_failed_node",
            DEVICE_ID: device.id,
            INCLUSION_STRATEGY: InclusionStrategy.DEFAULT.value,
            QR_CODE_STRING: "90testtesttesttesttesttesttesttesttesttesttesttesttest",
        }
    )

    msg = await ws_client.receive_json()
    assert not msg["success"]

    assert len(client.async_send_command.call_args_list) == 0

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_replace_failed_node",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 7,
                TYPE: "zwave_js/replace_failed_node",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 8,
            TYPE: "zwave_js/replace_failed_node",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_remove_failed_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    nortek_thermostat,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
    nortek_thermostat_removed_event,
    nortek_thermostat_added_event,
) -> None:
    """Test the remove_failed_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, nortek_thermostat)

    client.async_send_command.return_value = {"success": True}

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_remove_failed_node",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 1,
                TYPE: "zwave_js/remove_failed_node",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/remove_failed_node",
            DEVICE_ID: device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    # Create device registry entry for mock node
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-67")},
        name="Node 67",
    )

    # Fire node removed event
    client.driver.receive_event(nortek_thermostat_removed_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node removed"

    # Verify device was removed from device registry
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, "3245146787-67")},
        )
        is None
    )

    # Re-add node so we can test config entry not loaded
    client.driver.receive_event(nortek_thermostat_added_event)

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/remove_failed_node",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_begin_rebuilding_routes(
    hass: HomeAssistant,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the begin_rebuilding_routes websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/begin_rebuilding_routes",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_begin_rebuilding_routes",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/begin_rebuilding_routes",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/begin_rebuilding_routes",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_rebuild_routes_progress(
    hass: HomeAssistant,
    integration,
    client,
    nortek_thermostat,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the subscribe_rebuild_routes_progress command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_rebuild_routes_progress",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    # Fire rebuild routes progress
    event = Event(
        "rebuild routes progress",
        {
            "source": "controller",
            "event": "rebuild routes progress",
            "progress": {67: "pending"},
        },
    )
    client.driver.controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "rebuild routes progress"
    assert msg["event"]["rebuild_routes_status"] == {"67": "pending"}

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/subscribe_rebuild_routes_progress",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_rebuild_routes_progress_initial_value(
    hass: HomeAssistant,
    integration,
    client,
    nortek_thermostat,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribe_rebuild_routes_progress command when rebuild routes in progress."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    assert not client.driver.controller.rebuild_routes_progress

    # Fire rebuild routes progress before sending rebuild routes progress command
    event = Event(
        "rebuild routes progress",
        {
            "source": "controller",
            "event": "rebuild routes progress",
            "progress": {67: "pending"},
        },
    )
    client.driver.controller.receive_event(event)

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_rebuild_routes_progress",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"67": "pending"}


async def test_stop_rebuilding_routes(
    hass: HomeAssistant,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the stop_rebuilding_routes websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/stop_rebuilding_routes",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_stop_rebuilding_routes",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/stop_rebuilding_routes",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/stop_rebuilding_routes",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_rebuild_node_routes(
    hass: HomeAssistant,
    multisensor_6,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the rebuild_node_routes websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/rebuild_node_routes",
            DEVICE_ID: device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_rebuild_node_routes",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/rebuild_node_routes",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/rebuild_node_routes",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_refresh_node_info(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the refresh_node_info WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    device = get_device(hass, multisensor_6)

    client.async_send_command_no_wait.return_value = None
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/refresh_node_info",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.refresh_info"
    assert args["nodeId"] == 52

    event = Event(
        type="interview started",
        data={"source": "node", "event": "interview started", "nodeId": 52},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview started"

    event = Event(
        type="interview stage completed",
        data={
            "source": "node",
            "event": "interview stage completed",
            "stageName": "NodeInfo",
            "nodeId": 52,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview stage completed"
    assert msg["event"]["stage"] == "NodeInfo"

    event = Event(
        type="interview completed",
        data={"source": "node", "event": "interview completed", "nodeId": 52},
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview completed"

    event = Event(
        type="interview failed",
        data={
            "source": "node",
            "event": "interview failed",
            "nodeId": 52,
            "args": {
                "errorMessage": "error",
                "isFinal": True,
            },
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "interview failed"

    client.async_send_command_no_wait.reset_mock()

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/refresh_node_info",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_refresh_info",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 3,
                TYPE: "zwave_js/refresh_node_info",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/refresh_node_info",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_refresh_node_values(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the refresh_node_values WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    client.async_send_command_no_wait.return_value = None
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/refresh_node_values",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.refresh_values"
    assert args["nodeId"] == 52

    client.async_send_command_no_wait.reset_mock()

    # Test getting non-existent device fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/refresh_node_values",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_refresh_values",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/refresh_node_values",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/refresh_node_values",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_refresh_node_cc_values(
    hass: HomeAssistant,
    multisensor_6,
    client,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the refresh_node_cc_values WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    client.async_send_command_no_wait.return_value = None
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/refresh_node_cc_values",
            DEVICE_ID: device.id,
            COMMAND_CLASS_ID: 112,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.refresh_cc_values"
    assert args["nodeId"] == 52
    assert args["commandClass"] == 112

    client.async_send_command_no_wait.reset_mock()

    # Test using invalid CC ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/refresh_node_cc_values",
            DEVICE_ID: device.id,
            COMMAND_CLASS_ID: 9999,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test getting non-existent device fails
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/refresh_node_cc_values",
            DEVICE_ID: "fake_device",
            COMMAND_CLASS_ID: 112,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_refresh_cc_values",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/refresh_node_cc_values",
                DEVICE_ID: device.id,
                COMMAND_CLASS_ID: 112,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/refresh_node_cc_values",
            DEVICE_ID: device.id,
            COMMAND_CLASS_ID: 112,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_set_config_parameter(
    hass: HomeAssistant,
    multisensor_6,
    client,
    hass_ws_client: WebSocketGenerator,
    integration,
) -> None:
    """Test the set_config_parameter service."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)
    new_value_data = multisensor_6.values[
        get_value_id_str(multisensor_6, 112, 102, 0, 1)
    ].data.copy()
    new_value_data["endpoint"] = 1
    new_value = ConfigurationValue(multisensor_6, new_value_data)
    multisensor_6.values[get_value_id_str(multisensor_6, 112, 102, 1, 1)] = new_value

    client.async_send_command_no_wait.return_value = None

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/set_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: 1,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]["status"] == "queued"

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

    client.async_send_command_no_wait.return_value = None

    # Test using a different endpoint
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/set_config_parameter",
            DEVICE_ID: device.id,
            ENDPOINT: 1,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: 1,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]["status"] == "queued"

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 1,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

    # Test that hex strings are accepted and converted as expected
    client.async_send_command_no_wait.return_value = None

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/set_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: "0x1",
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]["status"] == "queued"

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 52
    assert args["valueId"] == {
        "commandClass": 112,
        "endpoint": 0,
        "property": 102,
        "propertyKey": 1,
    }
    assert args["value"] == 1

    client.async_send_command_no_wait.reset_mock()

    with patch(
        "homeassistant.components.zwave_js.api.async_set_config_parameter",
    ) as set_param_mock:
        set_param_mock.side_effect = InvalidNewValue("test")
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/set_config_parameter",
                DEVICE_ID: device.id,
                PROPERTY: 102,
                PROPERTY_KEY: 1,
                VALUE: 1,
            }
        )

        msg = await ws_client.receive_json()

        assert len(client.async_send_command_no_wait.call_args_list) == 0
        assert not msg["success"]
        assert msg["error"]["code"] == "not_supported"
        assert msg["error"]["message"] == "test"

        set_param_mock.side_effect = NotFoundError("test")
        await ws_client.send_json(
            {
                ID: 5,
                TYPE: "zwave_js/set_config_parameter",
                DEVICE_ID: device.id,
                PROPERTY: 102,
                PROPERTY_KEY: 1,
                VALUE: 1,
            }
        )

        msg = await ws_client.receive_json()

        assert len(client.async_send_command_no_wait.call_args_list) == 0
        assert not msg["success"]
        assert msg["error"]["code"] == "not_found"
        assert msg["error"]["message"] == "test"

        set_param_mock.side_effect = SetValueFailed("test")
        await ws_client.send_json(
            {
                ID: 6,
                TYPE: "zwave_js/set_config_parameter",
                DEVICE_ID: device.id,
                PROPERTY: 102,
                PROPERTY_KEY: 1,
                VALUE: 1,
            }
        )

        msg = await ws_client.receive_json()

        assert len(client.async_send_command_no_wait.call_args_list) == 0
        assert not msg["success"]
        assert msg["error"]["code"] == "unknown_error"
        assert msg["error"]["message"] == "test"

    # Test getting non-existent node fails
    await ws_client.send_json(
        {
            ID: 7,
            TYPE: "zwave_js/set_config_parameter",
            DEVICE_ID: "fake_device",
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: 1,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test FailedZWaveCommand is caught
    with patch(
        "homeassistant.components.zwave_js.api.async_set_config_parameter",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 8,
                TYPE: "zwave_js/set_config_parameter",
                DEVICE_ID: device.id,
                PROPERTY: 102,
                PROPERTY_KEY: 1,
                VALUE: 1,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 9,
            TYPE: "zwave_js/set_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
            PROPERTY_KEY: 1,
            VALUE: 1,
        }
    )

    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_get_config_parameters(
    hass: HomeAssistant, multisensor_6, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the get config parameters websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    node = multisensor_6
    device = get_device(hass, node)

    # Test getting configuration parameter values
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/get_config_parameters",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert len(result) == 61
    key = "52-112-0-2"
    assert result[key]["property"] == 2
    assert result[key]["property_key"] is None
    assert result[key]["endpoint"] == 0
    assert result[key]["configuration_value_type"] == "enumerated"
    assert result[key]["metadata"]["states"]
    assert (
        result[key]["metadata"]["description"]
        == "Stay awake for 10 minutes at power on"
    )
    assert result[key]["metadata"]["label"] == "Stay Awake in Battery Mode"
    assert result[key]["metadata"]["type"] == "number"
    assert result[key]["metadata"]["min"] == 0
    assert result[key]["metadata"]["max"] == 1
    assert result[key]["metadata"]["unit"] is None
    assert result[key]["metadata"]["writeable"] is True
    assert result[key]["metadata"]["readable"] is True
    assert result[key]["metadata"]["default"] == 0
    assert result[key]["value"] == 0

    key = "52-112-0-201-255"
    assert result[key]["property_key"] == 255

    # Test getting non-existent node config params fails
    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/get_config_parameters",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/get_config_parameters",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_set_raw_config_parameter(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the set_raw_config_parameter WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    # Change from async_send_command to async_send_command_no_wait
    client.async_send_command_no_wait.return_value = None

    # Test setting a raw config parameter value
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/set_raw_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
            VALUE: 1,
            VALUE_SIZE: 2,
            VALUE_FORMAT: 1,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]["status"] == "queued"

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.set_raw_config_parameter_value"
    assert args["nodeId"] == multisensor_6.node_id
    assert args["parameter"] == 102
    assert args["value"] == 1
    assert args["valueSize"] == 2
    assert args["valueFormat"] == 1

    # Reset the mock for async_send_command_no_wait instead
    client.async_send_command_no_wait.reset_mock()

    # Test getting non-existent node fails
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/set_raw_config_parameter",
            DEVICE_ID: "fake_device",
            PROPERTY: 102,
            VALUE: 1,
            VALUE_SIZE: 2,
            VALUE_FORMAT: 1,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/set_raw_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
            VALUE: 1,
            VALUE_SIZE: 2,
            VALUE_FORMAT: 1,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_get_raw_config_parameter(
    hass: HomeAssistant,
    multisensor_6,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the get_raw_config_parameter websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    client.async_send_command.return_value = {"value": 1}

    # Test getting a raw config parameter value
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/get_raw_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]["value"] == 1

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "endpoint.get_raw_config_parameter_value"
    assert args["nodeId"] == multisensor_6.node_id
    assert args["parameter"] == 102

    client.async_send_command.reset_mock()

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_get_raw_config_parameter_value",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/get_raw_config_parameter",
                DEVICE_ID: device.id,
                PROPERTY: 102,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test getting non-existent node fails
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/get_raw_config_parameter",
            DEVICE_ID: "fake_device",
            PROPERTY: 102,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test FailedCommand exception
    client.async_send_command.side_effect = FailedCommand("test", "test")
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/get_raw_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "test"
    assert msg["error"]["message"] == "Command failed: test"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/get_raw_config_parameter",
            DEVICE_ID: device.id,
            PROPERTY: 102,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


@pytest.mark.parametrize(
    ("firmware_data", "expected_data"),
    [({"target": "1"}, {"firmware_target": 1}), ({}, {})],
)
async def test_firmware_upload_view(
    hass: HomeAssistant,
    multisensor_6,
    integration,
    hass_client: ClientSessionGenerator,
    firmware_file,
    firmware_data: dict[str, Any],
    expected_data: dict[str, Any],
) -> None:
    """Test the HTTP firmware upload view."""
    client = await hass_client()
    device = get_device(hass, multisensor_6)
    with (
        patch(
            "homeassistant.components.zwave_js.api.update_firmware",
        ) as mock_node_cmd,
        patch(
            "homeassistant.components.zwave_js.api.controller_firmware_update_otw",
        ) as mock_controller_cmd,
        patch.dict(
            "homeassistant.components.zwave_js.api.USER_AGENT",
            {"HomeAssistant": "0.0.0"},
        ),
    ):
        data = {"file": firmware_file}
        data.update(firmware_data)

        resp = await client.post(
            f"/api/zwave_js/firmware/upload/{device.id}", data=data
        )

        update_data = NodeFirmwareUpdateData(
            "file", b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        for attr, value in expected_data.items():
            setattr(update_data, attr, value)

        mock_controller_cmd.assert_not_called()
        assert mock_node_cmd.call_args[0][1:3] == (multisensor_6, [update_data])
        assert mock_node_cmd.call_args[1] == {
            "additional_user_agent_components": {"HomeAssistant": "0.0.0"},
        }
        assert json.loads(await resp.text()) is None


async def test_firmware_upload_view_controller(
    hass: HomeAssistant,
    client,
    integration,
    hass_client: ClientSessionGenerator,
    firmware_file,
) -> None:
    """Test the HTTP firmware upload view for a controller."""
    hass_client = await hass_client()
    device = get_device(hass, client.driver.controller.nodes[1])
    with (
        patch(
            "homeassistant.components.zwave_js.api.update_firmware",
        ) as mock_node_cmd,
        patch(
            "homeassistant.components.zwave_js.api.controller_firmware_update_otw",
        ) as mock_controller_cmd,
        patch.dict(
            "homeassistant.components.zwave_js.api.USER_AGENT",
            {"HomeAssistant": "0.0.0"},
        ),
    ):
        resp = await hass_client.post(
            f"/api/zwave_js/firmware/upload/{device.id}",
            data={"file": firmware_file},
        )
        mock_node_cmd.assert_not_called()
        assert mock_controller_cmd.call_args[0][1:2] == (
            ControllerFirmwareUpdateData(
                "file", b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            ),
        )
        assert mock_controller_cmd.call_args[1] == {
            "additional_user_agent_components": {"HomeAssistant": "0.0.0"},
        }
        assert json.loads(await resp.text()) is None


async def test_firmware_upload_view_failed_command(
    hass: HomeAssistant,
    multisensor_6,
    integration,
    hass_client: ClientSessionGenerator,
    firmware_file,
) -> None:
    """Test failed command for the HTTP firmware upload view."""
    client = await hass_client()
    device = get_device(hass, multisensor_6)
    with patch(
        "homeassistant.components.zwave_js.api.update_firmware",
        side_effect=FailedCommand("test", "test"),
    ):
        resp = await client.post(
            f"/api/zwave_js/firmware/upload/{device.id}",
            data={"file": firmware_file},
        )
        assert resp.status == HTTPStatus.BAD_REQUEST


async def test_firmware_upload_view_invalid_payload(
    hass: HomeAssistant, multisensor_6, integration, hass_client: ClientSessionGenerator
) -> None:
    """Test an invalid payload for the HTTP firmware upload view."""
    device = get_device(hass, multisensor_6)
    client = await hass_client()
    resp = await client.post(
        f"/api/zwave_js/firmware/upload/{device.id}",
        data={"wrong_key": BytesIO(bytes(10))},
    )
    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_firmware_upload_view_no_driver(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the HTTP firmware upload view when the driver doesn't exist."""
    device = get_device(hass, multisensor_6)
    client.driver = None
    aiohttp_client = await hass_client()
    resp = await aiohttp_client.post(
        f"/api/zwave_js/firmware/upload/{device.id}",
        data={"wrong_key": BytesIO(bytes(10))},
    )
    assert resp.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("method", "url"),
    [("post", "/api/zwave_js/firmware/upload/{}")],
)
async def test_node_view_non_admin_user(
    hass: HomeAssistant,
    multisensor_6,
    integration,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    method,
    url,
) -> None:
    """Test node level views for non-admin users."""
    client = await hass_client()
    device = get_device(hass, multisensor_6)
    # Verify we require admin user
    hass_admin_user.groups = []
    resp = await client.request(method, url.format(device.id))
    assert resp.status == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("post", "/api/zwave_js/firmware/upload/{}"),
    ],
)
async def test_view_unloaded_config_entry(
    hass: HomeAssistant,
    multisensor_6,
    integration,
    hass_client: ClientSessionGenerator,
    method,
    url,
) -> None:
    """Test an unloaded config entry raises Bad Request."""
    client = await hass_client()
    device = get_device(hass, multisensor_6)
    await hass.config_entries.async_unload(integration.entry_id)
    resp = await client.request(method, url.format(device.id))
    assert resp.status == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    ("method", "url"),
    [("post", "/api/zwave_js/firmware/upload/INVALID")],
)
async def test_view_invalid_device_id(
    integration, hass_client: ClientSessionGenerator, method, url
) -> None:
    """Test an invalid device id parameter."""
    client = await hass_client()
    resp = await client.request(method, url.format(integration.entry_id))
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_subscribe_log_updates(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the subscribe_log_updates websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {}

    await ws_client.send_json(
        {ID: 1, TYPE: "zwave_js/subscribe_log_updates", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    event = Event(
        type="logging",
        data={
            "source": "driver",
            "event": "logging",
            "message": "test",
            "formattedMessage": "test",
            "direction": ">",
            "level": "debug",
            "primaryTags": "tag",
            "secondaryTags": "tag2",
            "secondaryTagPadding": 0,
            "multiline": False,
            "timestamp": "time",
            "label": "label",
            "context": {"source": "config"},
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "type": "log_message",
        "log_message": {
            "message": ["test"],
            "level": "debug",
            "primary_tags": "tag",
            "timestamp": "time",
        },
    }

    event = Event(
        type="log config updated",
        data={
            "source": "driver",
            "event": "log config updated",
            "config": {
                "enabled": False,
                "level": "error",
                "logToFile": True,
                "filename": "test",
                "forceConsole": True,
            },
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "type": "log_config",
        "log_config": {
            "enabled": False,
            "level": "error",
            "log_to_file": True,
            "filename": "test",
            "force_console": True,
        },
    }

    # Test FailedZWaveCommand is caught
    client.async_start_listening_logs.side_effect = FailedZWaveCommand(
        "failed_command", 1, "error message"
    )
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/subscribe_log_updates",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "zwave_error"
    assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {ID: 3, TYPE: "zwave_js/subscribe_log_updates", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_update_log_config(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that update_log_config WS API call and schema validation works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can set log level
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LEVEL: "Error"},
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "driver.update_log_config"
    assert args["config"] == {"level": "error"}

    client.async_send_command.reset_mock()

    # Test we can set logToFile to True
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LOG_TO_FILE: True, FILENAME: "/test"},
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "driver.update_log_config"
    assert args["config"] == {"logToFile": True, "filename": "/test"}

    client.async_send_command.reset_mock()

    # Test all parameters
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {
                LEVEL: "Error",
                LOG_TO_FILE: True,
                FILENAME: "/test",
                FORCE_CONSOLE: True,
                ENABLED: True,
            },
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "driver.update_log_config"
    assert args["config"] == {
        "level": "error",
        "logToFile": True,
        "filename": "/test",
        "forceConsole": True,
        "enabled": True,
    }

    client.async_send_command.reset_mock()

    # Test error when setting unrecognized log level
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LEVEL: "bad_log_level"},
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert "error" in msg and msg["error"]["code"] == "invalid_format"

    # Test error without service data
    await ws_client.send_json(
        {
            ID: 5,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {},
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert "error" in msg and "must contain at least one of" in msg["error"]["message"]

    # Test error if we set logToFile to True without providing filename
    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LOG_TO_FILE: True},
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert (
        "error" in msg
        and "must be provided if logging to file" in msg["error"]["message"]
    )

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_update_log_config",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 7,
                TYPE: "zwave_js/update_log_config",
                ENTRY_ID: entry.entry_id,
                CONFIG: {LEVEL: "Error"},
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 8,
            TYPE: "zwave_js/update_log_config",
            ENTRY_ID: entry.entry_id,
            CONFIG: {LEVEL: "Error"},
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_get_log_config(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the get_log_config WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can get log configuration
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/get_log_config",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"]
    assert msg["success"]

    log_config = msg["result"]
    assert log_config["enabled"]
    assert log_config["level"] == LogLevel.INFO
    assert log_config["log_to_file"] is False
    assert log_config["filename"] == ""
    assert log_config["force_console"] is False

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/get_log_config",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_data_collection(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the data collection WS API commands work."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"statisticsEnabled": False}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/data_collection_status",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result == {"opted_in": None, "enabled": False}

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "driver.is_statistics_enabled"
    }

    assert CONF_DATA_COLLECTION_OPTED_IN not in entry.data

    client.async_send_command.reset_mock()

    client.async_send_command.return_value = {}
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/update_data_collection_preference",
            ENTRY_ID: entry.entry_id,
            OPTED_IN: True,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result is None

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "driver.enable_statistics"
    assert args["applicationName"] == "Home Assistant"

    client.async_send_command.reset_mock()

    client.async_send_command.return_value = {}
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/update_data_collection_preference",
            ENTRY_ID: entry.entry_id,
            OPTED_IN: False,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result is None

    assert len(client.async_send_command.call_args_list) == 1
    assert client.async_send_command.call_args[0][0] == {
        "command": "driver.disable_statistics"
    }
    assert not entry.data[CONF_DATA_COLLECTION_OPTED_IN]

    client.async_send_command.reset_mock()

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_is_statistics_enabled",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 4,
                TYPE: "zwave_js/data_collection_status",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_enable_statistics",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 5,
                TYPE: "zwave_js/update_data_collection_preference",
                ENTRY_ID: entry.entry_id,
                OPTED_IN: True,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 6,
            TYPE: "zwave_js/data_collection_status",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {
            ID: 7,
            TYPE: "zwave_js/update_data_collection_preference",
            ENTRY_ID: entry.entry_id,
            OPTED_IN: True,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_abort_firmware_update(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the abort_firmware_update WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/abort_firmware_update",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.abort_firmware_update"
    assert args["nodeId"] == multisensor_6.node_id

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_abort_firmware_update",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/abort_firmware_update",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/abort_firmware_update",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    # Test sending command with improper device ID fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/abort_firmware_update",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_is_node_firmware_update_in_progress(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the is_firmware_update_in_progress WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    client.async_send_command.return_value = {"progress": True}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/is_node_firmware_update_in_progress",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.is_firmware_update_in_progress"
    assert args["nodeId"] == multisensor_6.node_id

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_is_firmware_update_in_progress",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/is_node_firmware_update_in_progress",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/is_node_firmware_update_in_progress",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_firmware_update_status(
    hass: HomeAssistant,
    multisensor_6,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the subscribe_firmware_update_status websocket command."""
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    client.async_send_command_no_wait.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            DEVICE_ID: device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": multisensor_6.node_id,
            "progress": {
                "currentFile": 1,
                "totalFiles": 1,
                "sentFragments": 1,
                "totalFragments": 10,
                "progress": 10.0,
            },
        },
    )
    multisensor_6.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update progress",
        "current_file": 1,
        "total_files": 1,
        "sent_fragments": 1,
        "total_fragments": 10,
        "progress": 10.0,
    }

    event = Event(
        type="firmware update finished",
        data={
            "source": "node",
            "event": "firmware update finished",
            "nodeId": multisensor_6.node_id,
            "result": {
                "status": 255,
                "success": True,
                "waitTime": 10,
                "reInterview": False,
            },
        },
    )
    multisensor_6.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update finished",
        "status": 255,
        "success": True,
        "wait_time": 10,
        "reinterview": False,
    }


async def test_subscribe_firmware_update_status_initial_value(
    hass: HomeAssistant,
    multisensor_6,
    client,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribe_firmware_update_status WS command with in progress update."""
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    assert multisensor_6.firmware_update_progress is None

    # Send a firmware update progress event before the WS command
    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": multisensor_6.node_id,
            "progress": {
                "currentFile": 1,
                "totalFiles": 1,
                "sentFragments": 1,
                "totalFragments": 10,
                "progress": 10.0,
            },
        },
    )
    multisensor_6.receive_event(event)

    client.async_send_command_no_wait.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            DEVICE_ID: device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update progress",
        "current_file": 1,
        "total_files": 1,
        "sent_fragments": 1,
        "total_fragments": 10,
        "progress": 10.0,
    }


async def test_subscribe_controller_firmware_update_status(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the subscribe_firmware_update_status websocket command for a node."""
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, client.driver.controller.nodes[1])

    client.async_send_command_no_wait.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            DEVICE_ID: device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    event = Event(
        type="firmware update progress",
        data={
            "source": "controller",
            "event": "firmware update progress",
            "progress": {
                "sentFragments": 1,
                "totalFragments": 10,
                "progress": 10.0,
            },
        },
    )
    client.driver.controller.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update progress",
        "current_file": 1,
        "total_files": 1,
        "sent_fragments": 1,
        "total_fragments": 10,
        "progress": 10.0,
    }

    event = Event(
        type="firmware update finished",
        data={
            "source": "controller",
            "event": "firmware update finished",
            "result": {
                "status": 255,
                "success": True,
            },
        },
    )
    client.driver.controller.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update finished",
        "status": 255,
        "success": True,
    }


async def test_subscribe_controller_firmware_update_status_initial_value(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribe_firmware_update_status cmd with in progress update for node."""
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, client.driver.controller.nodes[1])

    assert client.driver.controller.firmware_update_progress is None

    # Send a firmware update progress event before the WS command
    event = Event(
        type="firmware update progress",
        data={
            "source": "controller",
            "event": "firmware update progress",
            "progress": {
                "sentFragments": 1,
                "totalFragments": 10,
                "progress": 10.0,
            },
        },
    )
    client.driver.controller.receive_event(event)

    client.async_send_command_no_wait.return_value = {}

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            DEVICE_ID: device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "firmware update progress",
        "current_file": 1,
        "total_files": 1,
        "sent_fragments": 1,
        "total_fragments": 10,
        "progress": 10.0,
    }


async def test_subscribe_firmware_update_status_failures(
    hass: HomeAssistant,
    multisensor_6,
    client,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test failures for the subscribe_firmware_update_status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)
    # Test sending command with improper entry ID fails
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_firmware_update_status",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_get_node_firmware_update_capabilities(
    hass: HomeAssistant,
    client,
    multisensor_6,
    integration,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the get_node_firmware_update_capabilities WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    device = get_device(hass, multisensor_6)

    client.async_send_command.return_value = {
        "capabilities": {
            "firmwareUpgradable": True,
            "firmwareTargets": [0],
            "continuesToFunction": True,
            "supportsActivation": True,
        }
    }
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/get_node_firmware_update_capabilities",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "firmware_upgradable": True,
        "firmware_targets": [0],
        "continues_to_function": True,
        "supports_activation": True,
    }

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.get_firmware_update_capabilities"
    assert args["nodeId"] == multisensor_6.node_id

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.node.Node.async_get_firmware_update_capabilities",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/get_node_firmware_update_capabilities",
                DEVICE_ID: device.id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/get_node_firmware_update_capabilities",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    # Test sending command with improper device ID fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/get_node_firmware_update_capabilities",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_is_any_ota_firmware_update_in_progress(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the is_any_ota_firmware_update_in_progress WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"progress": True}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/is_any_ota_firmware_update_in_progress",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "controller.is_any_ota_firmware_update_in_progress"

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_is_any_ota_firmware_update_in_progress",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/is_any_ota_firmware_update_in_progress",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/is_any_ota_firmware_update_in_progress",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    # Test sending command with improper device ID fails
    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/is_any_ota_firmware_update_in_progress",
            ENTRY_ID: "invalid_entry",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_check_for_config_updates(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the check_for_config_updates WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can get log configuration
    client.async_send_command.return_value = {
        "updateAvailable": True,
        "newVersion": "test",
        "installedVersion": "test",
    }
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/check_for_config_updates",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"]
    assert msg["success"]

    config_update = msg["result"]
    assert config_update["update_available"]
    assert config_update["new_version"] == "test"

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_check_for_config_updates",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/check_for_config_updates",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/check_for_config_updates",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/check_for_config_updates",
            ENTRY_ID: "INVALID",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_install_config_update(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the install_config_update WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test we can get log configuration
    client.async_send_command.return_value = {"success": True}
    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/install_config_update",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"]
    assert msg["success"]

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_install_config_update",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json(
            {
                ID: 2,
                TYPE: "zwave_js/install_config_update",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/install_config_update",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/install_config_update",
            ENTRY_ID: "INVALID",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_subscribe_controller_statistics(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the subscribe_controller_statistics command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_controller_statistics",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "statistics updated",
        "source": "controller",
        "messages_tx": 0,
        "messages_rx": 0,
        "messages_dropped_tx": 0,
        "messages_dropped_rx": 0,
        "nak": 0,
        "can": 0,
        "timeout_ack": 0,
        "timout_response": 0,
        "timeout_callback": 0,
    }

    # Fire statistics updated
    event = Event(
        "statistics updated",
        {
            "source": "controller",
            "event": "statistics updated",
            "statistics": {
                "messagesTX": 1,
                "messagesRX": 1,
                "messagesDroppedTX": 1,
                "messagesDroppedRX": 1,
                "NAK": 1,
                "CAN": 1,
                "timeoutACK": 1,
                "timeoutResponse": 1,
                "timeoutCallback": 1,
            },
        },
    )
    client.driver.controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "statistics updated",
        "source": "controller",
        "messages_tx": 1,
        "messages_rx": 1,
        "messages_dropped_tx": 1,
        "messages_dropped_rx": 1,
        "nak": 1,
        "can": 1,
        "timeout_ack": 1,
        "timout_response": 1,
        "timeout_callback": 1,
    }

    # Test sending command with improper entry ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/subscribe_controller_statistics",
            ENTRY_ID: "fake_entry_id",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/subscribe_controller_statistics",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_subscribe_node_statistics(
    hass: HomeAssistant,
    multisensor_6,
    wallmote_central_scene,
    zen_31,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the subscribe_node_statistics command."""
    entry = integration
    ws_client = await hass_ws_client(hass)
    multisensor_6_device = get_device(hass, multisensor_6)
    zen_31_device = get_device(hass, zen_31)
    wallmote_central_scene_device = get_device(hass, wallmote_central_scene)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "zwave_js/subscribe_node_statistics",
            DEVICE_ID: multisensor_6_device.id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "source": "node",
        "event": "statistics updated",
        "nodeId": multisensor_6.node_id,
        "commands_tx": 0,
        "commands_rx": 0,
        "commands_dropped_tx": 0,
        "commands_dropped_rx": 0,
        "timeout_response": 0,
        "rtt": None,
        "rssi": None,
        "lwr": None,
        "nlwr": None,
    }

    # Fire statistics updated
    event = Event(
        "statistics updated",
        {
            "source": "node",
            "event": "statistics updated",
            "nodeId": multisensor_6.node_id,
            "statistics": {
                "commandsTX": 1,
                "commandsRX": 2,
                "commandsDroppedTX": 3,
                "commandsDroppedRX": 4,
                "timeoutResponse": 5,
                "rtt": 6,
                "rssi": 7,
                "lwr": {
                    "protocolDataRate": 1,
                    "rssi": 1,
                    "repeaters": [wallmote_central_scene.node_id],
                    "repeaterRSSI": [1],
                    "routeFailedBetween": [
                        zen_31.node_id,
                        multisensor_6.node_id,
                    ],
                },
                "nlwr": {
                    "protocolDataRate": 2,
                    "rssi": 2,
                    "repeaters": [],
                    "repeaterRSSI": [127],
                    "routeFailedBetween": [
                        multisensor_6.node_id,
                        zen_31.node_id,
                    ],
                },
            },
        },
    )
    client.driver.controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "statistics updated",
        "source": "node",
        "node_id": multisensor_6.node_id,
        "commands_tx": 1,
        "commands_rx": 2,
        "commands_dropped_tx": 3,
        "commands_dropped_rx": 4,
        "timeout_response": 5,
        "rtt": 6,
        "rssi": 7,
        "lwr": {
            "protocol_data_rate": 1,
            "rssi": 1,
            "repeaters": [wallmote_central_scene_device.id],
            "repeater_rssi": [1],
            "route_failed_between": [
                zen_31_device.id,
                multisensor_6_device.id,
            ],
        },
        "nlwr": {
            "protocol_data_rate": 2,
            "rssi": 2,
            "repeaters": [],
            "repeater_rssi": [127],
            "route_failed_between": [
                multisensor_6_device.id,
                zen_31_device.id,
            ],
        },
    }

    # Test sending command with improper entry ID fails
    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "zwave_js/subscribe_node_statistics",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json(
        {
            ID: 4,
            TYPE: "zwave_js/subscribe_node_statistics",
            DEVICE_ID: multisensor_6_device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_hard_reset_controller(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the hard_reset_controller WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    async def async_send_command_driver_ready(
        message: dict[str, Any],
        require_schema: int | None = None,
    ) -> dict:
        """Send a command and get a response."""
        client.driver.emit(
            "driver ready", {"event": "driver ready", "source": "driver"}
        )
        return {}

    client.async_send_command.side_effect = async_send_command_driver_ready

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/hard_reset_controller",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, client.driver.controller.nodes[1])}
    )
    assert device is not None
    assert msg["result"] == device.id
    assert msg["success"]

    assert client.async_send_command.call_count == 3
    # The first call is the relevant hard reset command.
    # 25 is the require_schema parameter.
    assert client.async_send_command.call_args_list[0] == call(
        {"command": "driver.hard_reset"}, 25
    )

    client.async_send_command.reset_mock()

    # Test sending command with driver not ready and timeout.

    async def async_send_command_no_driver_ready(
        message: dict[str, Any],
        require_schema: int | None = None,
    ) -> dict:
        """Send a command and get a response."""
        return {}

    client.async_send_command.side_effect = async_send_command_no_driver_ready

    with patch(
        "homeassistant.components.zwave_js.api.HARD_RESET_CONTROLLER_DRIVER_READY_TIMEOUT",
        new=0,
    ):
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/hard_reset_controller",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

    device = device_registry.async_get_device(
        identifiers={get_device_id(client.driver, client.driver.controller.nodes[1])}
    )
    assert device is not None
    assert msg["result"] == device.id
    assert msg["success"]

    assert client.async_send_command.call_count == 3
    # The first call is the relevant hard reset command.
    # 25 is the require_schema parameter.
    assert client.async_send_command.call_args_list[0] == call(
        {"command": "driver.hard_reset"}, 25
    )

    # Test FailedZWaveCommand is caught
    with patch(
        "zwave_js_server.model.driver.Driver.async_hard_reset",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/hard_reset_controller",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/hard_reset_controller",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/hard_reset_controller",
            ENTRY_ID: "INVALID",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_node_capabilities(
    hass: HomeAssistant,
    multisensor_6: Node,
    integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the node_capabilities websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    node = multisensor_6
    device = get_device(hass, node)
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/node_capabilities",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["result"] == {
        "0": [
            {
                "id": 113,
                "name": "Notification",
                "version": 8,
                "isSecure": False,
                "is_secure": False,
            }
        ]
    }

    # Test getting non-existent node fails
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/node_status",
            DEVICE_ID: "fake_device",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/node_status",
            DEVICE_ID: device.id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED


async def test_invoke_cc_api(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the invoke_cc_api websocket command."""
    ws_client = await hass_ws_client(hass)

    device_radio_thermostat = get_device(
        hass, climate_radio_thermostat_ct100_plus_different_endpoints
    )
    assert device_radio_thermostat

    # Test successful invoke_cc_api call with a static endpoint
    client.async_send_command.return_value = {"response": True}
    client.async_send_command_no_wait.return_value = {"response": True}

    # Test with wait_for_result=False (default)
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/invoke_cc_api",
            DEVICE_ID: device_radio_thermostat.id,
            ATTR_COMMAND_CLASS: 67,
            ATTR_METHOD_NAME: "someMethod",
            ATTR_PARAMETERS: [1, 2],
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None  # We did not specify wait_for_result=True

    await hass.async_block_till_done()

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args == {
        "command": "endpoint.invoke_cc_api",
        "nodeId": 26,
        "endpoint": 0,
        "commandClass": 67,
        "methodName": "someMethod",
        "args": [1, 2],
    }

    client.async_send_command_no_wait.reset_mock()

    # Test with wait_for_result=True
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/invoke_cc_api",
            DEVICE_ID: device_radio_thermostat.id,
            ATTR_COMMAND_CLASS: 67,
            ATTR_ENDPOINT: 0,
            ATTR_METHOD_NAME: "someMethod",
            ATTR_PARAMETERS: [1, 2],
            ATTR_WAIT_FOR_RESULT: True,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is True

    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args == {
        "command": "endpoint.invoke_cc_api",
        "nodeId": 26,
        "endpoint": 0,
        "commandClass": 67,
        "methodName": "someMethod",
        "args": [1, 2],
    }

    client.async_send_command.side_effect = NotFoundError

    # Ensure an error is returned
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/invoke_cc_api",
            DEVICE_ID: device_radio_thermostat.id,
            ATTR_COMMAND_CLASS: 67,
            ATTR_ENDPOINT: 0,
            ATTR_METHOD_NAME: "someMethod",
            ATTR_PARAMETERS: [1, 2],
            ATTR_WAIT_FOR_RESULT: True,
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {"code": "NotFoundError", "message": ""}


@pytest.mark.parametrize(
    ("config", "installer_mode"), [({}, False), ({CONF_INSTALLER_MODE: True}, True)]
)
async def test_get_integration_settings(
    config: dict[str, Any],
    installer_mode: bool,
    hass: HomeAssistant,
    client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the get_integration_settings WS API call works."""
    ws_client = await hass_ws_client(hass)

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/get_integration_settings",
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        CONF_INSTALLER_MODE: installer_mode,
    }


async def test_backup_nvm(
    hass: HomeAssistant,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the backup NVM websocket command."""
    ws_client = await hass_ws_client(hass)

    # Set up mocks for the controller events
    controller = client.driver.controller

    # Test subscription and events
    with patch.object(
        controller, "async_backup_nvm_raw_base64", return_value="test"
    ) as mock_backup:
        # Send the subscription request
        await ws_client.send_json_auto_id(
            {
                "type": "zwave_js/backup_nvm",
                "entry_id": integration.entry_id,
            }
        )

        # Verify the finished event with data first
        msg = await ws_client.receive_json()
        assert msg["type"] == "event"
        assert msg["event"]["event"] == "finished"
        assert msg["event"]["data"] == "test"

        # Verify subscription success
        msg = await ws_client.receive_json()
        assert msg["type"] == "result"
        assert msg["success"] is True

        # Simulate progress events
        event = Event(
            "nvm backup progress",
            {
                "source": "controller",
                "event": "nvm backup progress",
                "bytesRead": 25,
                "total": 100,
            },
        )
        controller.receive_event(event)
        msg = await ws_client.receive_json()
        assert msg["event"]["event"] == "nvm backup progress"
        assert msg["event"]["bytesRead"] == 25
        assert msg["event"]["total"] == 100

        event = Event(
            "nvm backup progress",
            {
                "source": "controller",
                "event": "nvm backup progress",
                "bytesRead": 50,
                "total": 100,
            },
        )
        controller.receive_event(event)
        msg = await ws_client.receive_json()
        assert msg["event"]["event"] == "nvm backup progress"
        assert msg["event"]["bytesRead"] == 50
        assert msg["event"]["total"] == 100

        # Wait for the backup to complete
        await hass.async_block_till_done()

        # Verify the backup was called
        assert mock_backup.called

    # Test backup failure
    with patch.object(
        controller,
        "async_backup_nvm_raw_base64",
        side_effect=FailedCommand("failed_command", "Backup failed"),
    ):
        # Send the subscription request
        await ws_client.send_json_auto_id(
            {
                "type": "zwave_js/backup_nvm",
                "entry_id": integration.entry_id,
            }
        )

        # Verify error response
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "Backup failed"

    # Test config entry not found
    await ws_client.send_json_auto_id(
        {
            "type": "zwave_js/backup_nvm",
            "entry_id": "invalid_entry_id",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"

    # Test config entry not loaded
    await hass.config_entries.async_unload(integration.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            "type": "zwave_js/backup_nvm",
            "entry_id": integration.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["error"]["code"] == "not_loaded"


async def test_restore_nvm(
    hass: HomeAssistant,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the restore NVM websocket command."""
    ws_client = await hass_ws_client(hass)

    # Set up mocks for the controller events
    controller = client.driver.controller

    async def async_send_command_driver_ready(
        message: dict[str, Any],
        require_schema: int | None = None,
    ) -> dict:
        """Send a command and get a response."""
        client.driver.emit(
            "driver ready", {"event": "driver ready", "source": "driver"}
        )
        return {}

    client.async_send_command.side_effect = async_send_command_driver_ready

    # Send the subscription request
    await ws_client.send_json_auto_id(
        {
            "type": "zwave_js/restore_nvm",
            "entry_id": integration.entry_id,
            "data": "dGVzdA==",  # base64 encoded "test"
        }
    )

    # Verify the finished event first
    msg = await ws_client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["event"] == "finished"

    # Verify subscription success
    msg = await ws_client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"] is True

    # Simulate progress events
    event = Event(
        "nvm restore progress",
        {
            "source": "controller",
            "event": "nvm restore progress",
            "bytesWritten": 25,
            "total": 100,
        },
    )
    controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "nvm restore progress"
    assert msg["event"]["bytesWritten"] == 25
    assert msg["event"]["total"] == 100

    event = Event(
        "nvm restore progress",
        {
            "source": "controller",
            "event": "nvm restore progress",
            "bytesWritten": 50,
            "total": 100,
        },
    )
    controller.receive_event(event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "nvm restore progress"
    assert msg["event"]["bytesWritten"] == 50
    assert msg["event"]["total"] == 100

    await hass.async_block_till_done()

    # Verify the restore was called
    # The first call is the relevant one for nvm restore.
    assert client.async_send_command.call_count == 3
    assert client.async_send_command.call_args_list[0] == call(
        {
            "command": "controller.restore_nvm",
            "nvmData": "dGVzdA==",
        },
        require_schema=14,
    )

    client.async_send_command.reset_mock()

    # Test sending command with driver not ready and timeout.

    async def async_send_command_no_driver_ready(
        message: dict[str, Any],
        require_schema: int | None = None,
    ) -> dict:
        """Send a command and get a response."""
        return {}

    client.async_send_command.side_effect = async_send_command_no_driver_ready

    with patch(
        "homeassistant.components.zwave_js.api.RESTORE_NVM_DRIVER_READY_TIMEOUT",
        new=0,
    ):
        # Send the subscription request
        await ws_client.send_json_auto_id(
            {
                "type": "zwave_js/restore_nvm",
                "entry_id": integration.entry_id,
                "data": "dGVzdA==",  # base64 encoded "test"
            }
        )

        # Verify the finished event first
        msg = await ws_client.receive_json()

        assert msg["type"] == "event"
        assert msg["event"]["event"] == "finished"

        # Verify subscription success
        msg = await ws_client.receive_json()
        assert msg["type"] == "result"
        assert msg["success"] is True

        await hass.async_block_till_done()

    # Verify the restore was called
    # The first call is the relevant one for nvm restore.
    assert client.async_send_command.call_count == 3
    assert client.async_send_command.call_args_list[0] == call(
        {
            "command": "controller.restore_nvm",
            "nvmData": "dGVzdA==",
        },
        require_schema=14,
    )

    client.async_send_command.reset_mock()

    # Test restore failure
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_restore_nvm_base64",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        # Send the subscription request
        await ws_client.send_json_auto_id(
            {
                "type": "zwave_js/restore_nvm",
                "entry_id": integration.entry_id,
                "data": "dGVzdA==",  # base64 encoded "test"
            }
        )

        # Verify error response
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"

    # Test entry_id not found
    await ws_client.send_json_auto_id(
        {
            "type": "zwave_js/restore_nvm",
            "entry_id": "invalid_entry_id",
            "data": "dGVzdA==",  # base64 encoded "test"
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"

    # Test config entry not loaded
    await hass.config_entries.async_unload(integration.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            "type": "zwave_js/restore_nvm",
            "entry_id": integration.entry_id,
            "data": "dGVzdA==",  # base64 encoded "test"
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_cancel_secure_bootstrap_s2(
    hass: HomeAssistant, client, integration, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that the cancel_secure_bootstrap_s2 WS API call works."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Test successful cancellation
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/cancel_secure_bootstrap_s2",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "controller.cancel_secure_bootstrap_s2"

    # Test FailedZWaveCommand is caught
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_cancel_secure_bootstrap_s2",
        side_effect=FailedZWaveCommand("failed_command", 1, "error message"),
    ):
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/cancel_secure_bootstrap_s2",
                ENTRY_ID: entry.entry_id,
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == "zwave_error"
        assert msg["error"]["message"] == "zwave_error: Z-Wave error 1 - error message"

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/cancel_secure_bootstrap_s2",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    # Test sending command with invalid entry ID fails
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/cancel_secure_bootstrap_s2",
            ENTRY_ID: "invalid_entry_id",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_subscribe_s2_inclusion(
    hass: HomeAssistant, integration, client, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the subscribe_s2_inclusion websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/subscribe_s2_inclusion",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    # Test receiving requested grant event
    event = Event(
        type="grant security classes",
        data={
            "source": "controller",
            "event": "grant security classes",
            "requested": {
                "securityClasses": [SecurityClass.S2_UNAUTHENTICATED],
                "clientSideAuth": False,
            },
        },
    )
    client.driver.receive_event(event)

    # Test receiving DSK request event
    event = Event(
        type="validate dsk and enter pin",
        data={
            "source": "controller",
            "event": "validate dsk and enter pin",
            "dsk": "test_dsk",
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"] == {
        "event": "validate dsk and enter pin",
        "dsk": "test_dsk",
    }

    # Test sending command with not loaded entry fails
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/subscribe_s2_inclusion",
            ENTRY_ID: entry.entry_id,
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_LOADED

    # Test invalid config entry id
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/subscribe_s2_inclusion",
            ENTRY_ID: "INVALID",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND


async def test_lookup_device(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test lookup_device websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    # Create mock device response
    mock_device = MagicMock()
    mock_device.to_dict.return_value = {
        "manufacturer": "Test Manufacturer",
        "label": "Test Device",
        "description": "Test Device Description",
        "devices": [{"productType": 1, "productId": 2}],
        "firmwareVersion": {"min": "1.0", "max": "2.0"},
    }

    # Test successful lookup
    client.driver.config_manager.lookup_device = AsyncMock(return_value=mock_device)

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/lookup_device",
            ENTRY_ID: entry.entry_id,
            MANUFACTURER_ID: 1,
            PRODUCT_TYPE: 2,
            PRODUCT_ID: 3,
            APPLICATION_VERSION: "1.5",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == mock_device.to_dict.return_value

    client.driver.config_manager.lookup_device.assert_called_once_with(1, 2, 3, "1.5")

    # Reset mock
    client.driver.config_manager.lookup_device.reset_mock()

    # Test lookup without optional application_version
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/lookup_device",
            ENTRY_ID: entry.entry_id,
            MANUFACTURER_ID: 4,
            PRODUCT_TYPE: 5,
            PRODUCT_ID: 6,
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert msg["result"] == mock_device.to_dict.return_value

    client.driver.config_manager.lookup_device.assert_called_once_with(4, 5, 6, None)

    # Test device not found
    with patch.object(
        client.driver.config_manager,
        "lookup_device",
        return_value=None,
    ):
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/lookup_device",
                ENTRY_ID: entry.entry_id,
                MANUFACTURER_ID: 99,
                PRODUCT_TYPE: 99,
                PRODUCT_ID: 99,
                APPLICATION_VERSION: "9.9",
            }
        )
        msg = await ws_client.receive_json()

        assert not msg["success"]
        assert msg["error"]["code"] == ERR_NOT_FOUND
        assert msg["error"]["message"] == "Device not found"

    # Test sending command with improper entry ID fails
    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/lookup_device",
            ENTRY_ID: "invalid_entry_id",
            MANUFACTURER_ID: 1,
            PRODUCT_TYPE: 1,
            PRODUCT_ID: 1,
            APPLICATION_VERSION: "1.0",
        }
    )
    msg = await ws_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_FOUND
    assert msg["error"]["message"] == "Config entry invalid_entry_id not found"

    # Test FailedCommand exception
    error_message = "Failed to execute lookup_device command"
    with patch.object(
        client.driver.config_manager,
        "lookup_device",
        side_effect=FailedCommand("lookup_device", error_message),
    ):
        # Send the subscription request
        await ws_client.send_json_auto_id(
            {
                TYPE: "zwave_js/lookup_device",
                ENTRY_ID: entry.entry_id,
                MANUFACTURER_ID: 1,
                PRODUCT_TYPE: 2,
                PRODUCT_ID: 3,
                APPLICATION_VERSION: "1.0",
            }
        )

        # Verify error response
        msg = await ws_client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == error_message
        assert msg["error"]["message"] == f"Command failed: {error_message}"


async def test_subscribe_new_devices(
    hass: HomeAssistant,
    integration,
    client,
    hass_ws_client: WebSocketGenerator,
    multisensor_6_state,
) -> None:
    """Test the subscribe_new_devices websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json_auto_id(
        {
            TYPE: "zwave_js/subscribe_new_devices",
            ENTRY_ID: entry.entry_id,
        }
    )

    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    # Simulate a device being registered
    node = Node(client, deepcopy(multisensor_6_state))
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    # Verify we receive the expected message
    msg = await ws_client.receive_json()
    assert msg["type"] == "event"
    assert msg["event"]["event"] == "device registered"
    assert msg["event"]["device"]["name"] == node.device_config.description
    assert msg["event"]["device"]["manufacturer"] == node.device_config.manufacturer
    assert msg["event"]["device"]["model"] == node.device_config.label
