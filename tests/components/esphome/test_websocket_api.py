"""Tests for ESPHome websocket API."""

import asyncio
import importlib
import sys
import threading
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aioesphomeapi import (
    APIClient,
    APIConnectionError,
    APIVersion,
    BinarySensorInfo,
    DeviceCapabilities,
    DeviceInfo,
    DeviceWizard,
    EntityInfo,
    SendspinFeature,
    SwitchInfo,
    UnsupportedWizardVersionError,
)
from aioesphomeapi.model import (
    SendspinPairingTokenResponse,
    SendspinPairingTokenStatus,
    SerialProxyPortType,
    SubDeviceInfo,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import MockHAClientWebSocket, WebSocketGenerator

from homeassistant.components.esphome.const import CONF_NOISE_PSK, DOMAIN
from homeassistant.components.esphome.serial_proxy import build_url
from homeassistant.components.esphome.websocket_api import (
    CLIENT_ID,
    CLIENT_IDS,
    DEVICE_ID,
    ENTRY_ID,
    TYPE,
)
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntryDisabler
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MockESPHomeDeviceType


def _device_id_for_mac(
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
    mac: str = "11:22:33:44:55:aa",
) -> str:
    """Return the device registry id for an ESPHome MAC."""
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
    )
    assert device is not None
    return device.id


async def test_get_encryption_key(
    mock_client: APIClient,
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get encryption key."""
    mock_config_entry = init_integration

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_encryption_key",
            ENTRY_ID: mock_config_entry.entry_id,
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {
        "encryption_key": mock_config_entry.data.get(CONF_NOISE_PSK)
    }


async def test_get_device_capabilities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the cached device capabilities."""
    mock_client.connected_address = "192.168.1.2"
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities={
            "bluetooth_proxy": {"feature_flags": 1},
            "zwave_proxy": {"feature_flags": 1, "home_id": 1234567890},
            "serial_proxies": [
                {"name": "uart0", "port_type": SerialProxyPortType.TTL},
                {"name": "amp", "port_type": SerialProxyPortType.RS232},
                {"name": "bus", "port_type": SerialProxyPortType.RS485},
                {"name": "unknown", "port_type": None},
            ],
            "sendspin": {"feature_flags": SendspinFeature.PAIRING_TOKEN},
        },
    )

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )

    mock_client.device_capabilities_compat.assert_awaited_once_with(device.device_info)
    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {
        "bluetooth_proxy": {"supported": True},
        "zwave_proxy": {
            "supported": True,
            "home_id": 1234567890,
            "config_entry_id": None,
        },
        "serial_proxies": [
            {
                "name": "uart0",
                "port_type": "TTL",
                "url": str(build_url(device.entry.entry_id, port_name="uart0")),
            },
            {
                "name": "amp",
                "port_type": "RS232",
                "url": str(build_url(device.entry.entry_id, port_name="amp")),
            },
            {
                "name": "bus",
                "port_type": "RS485",
                "url": str(build_url(device.entry.entry_id, port_name="bus")),
            },
            {
                "name": "unknown",
                "port_type": None,
                "url": str(build_url(device.entry.entry_id, port_name="unknown")),
            },
        ],
        "sendspin": {"supported": True},
    }


@pytest.mark.parametrize(
    "command", ["esphome/get_device_capabilities", "esphome/get_device_wizard"]
)
async def test_device_commands_device_not_found(
    init_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    command: str,
) -> None:
    """Test the device commands when the device registry id is unknown."""
    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: command,
            DEVICE_ID: "not-a-device",
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["message"] == "Device not found"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        pytest.param(
            "esphome/get_device_capabilities",
            {
                "bluetooth_proxy": {"supported": False},
                "zwave_proxy": {
                    "supported": False,
                    "home_id": 0,
                    "config_entry_id": None,
                },
                "serial_proxies": [],
                "sendspin": {"supported": False},
            },
            id="capabilities",
        ),
        pytest.param("esphome/get_device_wizard", {"pages": []}, id="wizard"),
    ],
)
async def test_device_commands_entry_not_loaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    command: str,
    expected: dict[str, Any],
) -> None:
    """Test the device commands report nothing while the entry is not loaded."""
    mock_client.device_wizard = AsyncMock(return_value=DeviceWizard.from_dict(WIZARD))
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=WIZARD_SWITCHES,
        device_capabilities={
            "bluetooth_proxy": {"feature_flags": 1},
            "wizard": {"configured": True},
        },
    )
    await hass.config_entries.async_unload(device.entry.entry_id)
    await hass.async_block_till_done()

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: command,
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == expected


async def test_get_device_capabilities_wrong_domain(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get_device_capabilities when the device is not ESPHome."""
    other_entry = MockConfigEntry(domain="switch", data={})
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")},
    )

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: device.id,
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["message"] == "Device is not an ESPHome device"


async def test_get_device_capabilities_sub_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test capabilities are not exposed on ESPHome sub-devices."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "devices": [
                SubDeviceInfo(device_id=11111111, name="Motion Sensor", area_id=0),
            ],
        },
    )

    sub_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{device.device_info.mac_address}_11111111"), device.entry.entry_id
    )
    assert sub_device is not None

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: sub_device.id,
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["message"] == "Device is not the main ESPHome device"


async def test_get_device_capabilities_unavailable(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test capabilities are kept while disconnected and fetched again on reconnect."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities={
            "bluetooth_proxy": {"feature_flags": 1},
            "sendspin": {"feature_flags": SendspinFeature.PAIRING_TOKEN},
        },
    )
    get_capabilities = {
        TYPE: "esphome/get_device_capabilities",
        DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
    }
    websocket_client = await hass_ws_client()

    # Sendspin is only in the capabilities, not in the stored DeviceInfo
    await device.mock_disconnect(False)
    await websocket_client.send_json_auto_id(get_capabilities)
    response = await websocket_client.receive_json()
    assert response["result"]["bluetooth_proxy"] == {"supported": True}
    assert response["result"]["sendspin"] == {"supported": True}

    # A firmware update can change them while the device is away
    mock_client.device_capabilities_compat.return_value = DeviceCapabilities()
    await device.mock_connect()
    await websocket_client.send_json_auto_id(get_capabilities)
    response = await websocket_client.receive_json()
    assert response["result"]["bluetooth_proxy"] == {"supported": False}
    assert response["result"]["sendspin"] == {"supported": False}


@pytest.mark.parametrize(
    ("stored_data", "expected"),
    [
        pytest.param(
            {
                "device_capabilities": {
                    "zwave_proxy": {"feature_flags": 1, "home_id": 1234567890},
                    "serial_proxies": [
                        {"name": "uart0", "port_type": SerialProxyPortType.TTL}
                    ],
                    "sendspin": {"feature_flags": SendspinFeature.PAIRING_TOKEN},
                }
            },
            {
                "bluetooth_proxy": {"supported": False},
                "zwave_proxy": {
                    "supported": True,
                    "home_id": 1234567890,
                    "config_entry_id": None,
                },
                "serial_proxies": [
                    {
                        "name": "uart0",
                        "port_type": "TTL",
                        "url": "esphome-hass://esphome/restored_entry?port_name=uart0",
                    }
                ],
                "sendspin": {"supported": True},
            },
            id="stored",
        ),
        pytest.param(
            {},
            {
                "bluetooth_proxy": {"supported": False},
                "zwave_proxy": {
                    "supported": False,
                    "home_id": 0,
                    "config_entry_id": None,
                },
                "serial_proxies": [],
                "sendspin": {"supported": False},
            },
            id="stored_before_capabilities",
        ),
    ],
)
async def test_get_device_capabilities_restored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    stored_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test capabilities are restored from storage before the device connects."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="restored_entry",
        unique_id="11:22:33:44:55:aa",
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:aa")},
    )
    device_info = DeviceInfo(name="test", mac_address="11:22:33:44:55:AA")
    storage_key = f"{DOMAIN}.{entry.entry_id}"
    hass_storage[storage_key] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key,
        "data": {
            "device_info": device_info.to_dict(),
            "api_version": APIVersion(1, 15).to_dict(),
            **stored_data,
        },
    }
    connect_event = asyncio.Event()

    async def _blocked_connect() -> tuple[DeviceInfo, list[Any], list[Any]]:
        await connect_event.wait()
        return (device_info, [], [])

    mock_client.device_info_and_list_entities = _blocked_connect
    assert await hass.config_entries.async_setup(entry.entry_id)

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {TYPE: "esphome/get_device_capabilities", DEVICE_ID: device.id}
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == expected

    connect_event.set()
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("zwave_entries", "home_id", "config_entry_id"),
    [
        pytest.param(
            [{"entry_id": "zwave", "unique_id": "1234567890"}],
            1234567890,
            "zwave",
            id="configured",
        ),
        pytest.param(
            [{"entry_id": "zwave", "unique_id": 1234567890}],
            1234567890,
            "zwave",
            id="legacy_int_unique_id",
        ),
        pytest.param(
            [
                {"unique_id": "1234567890", "source": SOURCE_IGNORE},
                {"entry_id": "zwave", "unique_id": "1234567890"},
            ],
            1234567890,
            "zwave",
            id="ignored_duplicate",
        ),
        pytest.param([{"unique_id": "999"}], 1234567890, None, id="other_network"),
        pytest.param(
            [{"unique_id": "1234567890", "source": SOURCE_IGNORE}],
            1234567890,
            None,
            id="ignored",
        ),
        pytest.param(
            [{"unique_id": "1234567890", "disabled_by": ConfigEntryDisabler.USER}],
            1234567890,
            None,
            id="disabled",
        ),
        pytest.param([{"unique_id": "0"}], 0, None, id="home_id_zero"),
    ],
)
async def test_get_device_capabilities_zwave_js_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    zwave_entries: list[dict[str, Any]],
    home_id: int,
    config_entry_id: str | None,
) -> None:
    """Test matching the advertised home ID to a zwave_js config entry."""
    for entry_kwargs in zwave_entries:
        MockConfigEntry(domain="zwave_js", **entry_kwargs).add_to_hass(hass)
    mock_client.connected_address = "192.168.1.2"
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities={"zwave_proxy": {"feature_flags": 1, "home_id": home_id}},
    )

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_capabilities",
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )
    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"]["zwave_proxy"] == {
        "supported": True,
        "home_id": home_id,
        "config_entry_id": config_entry_id,
    }


WIZARD = {
    "pages": [
        {
            "title": "Bluetooth",
            "description": "Choose whether this device offers Bluetooth.",
            "entities": [{"key": 3, "description": "Proxies Bluetooth devices."}],
        },
        {
            "title": "Sendspin",
            "description": "Choose how this device works with Sendspin.",
            "entities": [
                {"key": 2, "description": "Lets Sendspin servers play audio."},
                {"key": 99, "description": "Not exposed by the device."},
            ],
        },
    ]
}
WIZARD_SWITCHES = [
    SwitchInfo(object_id="sendspin", key=2, name="Sendspin"),
    SwitchInfo(object_id="bluetooth", key=3, name="Bluetooth"),
]
WIZARD_PAGES = [
    {
        "title": "Bluetooth",
        "description": "Choose whether this device offers Bluetooth.",
        "entities": [
            {
                "entity_id": "switch.test_bluetooth",
                "description": "Proxies Bluetooth devices.",
            }
        ],
    },
    {
        "title": "Sendspin",
        "description": "Choose how this device works with Sendspin.",
        "entities": [
            {
                "entity_id": "switch.test_sendspin",
                "description": "Lets Sendspin servers play audio.",
            },
            {"entity_id": None, "description": "Not exposed by the device."},
        ],
    },
]


@pytest.mark.parametrize(
    ("device_wizard", "entity_info", "expected_pages", "stored"),
    [
        pytest.param(
            {"return_value": DeviceWizard.from_dict(WIZARD)},
            WIZARD_SWITCHES,
            WIZARD_PAGES,
            True,
            id="wizard",
        ),
        pytest.param(
            {"return_value": DeviceWizard.from_dict(WIZARD)},
            [
                *WIZARD_SWITCHES,
                BinarySensorInfo(object_id="bluetooth", key=3, name="Bluetooth"),
            ],
            [
                {
                    **WIZARD_PAGES[0],
                    "entities": [
                        {"entity_id": None, "description": "Proxies Bluetooth devices."}
                    ],
                },
                WIZARD_PAGES[1],
            ],
            True,
            id="key_on_two_platforms",
        ),
        pytest.param(
            {"side_effect": UnsupportedWizardVersionError(2)},
            WIZARD_SWITCHES,
            [],
            False,
            id="newer_wizard_format",
        ),
    ],
)
async def test_get_device_wizard(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    device_wizard: dict[str, Any],
    entity_info: list[EntityInfo],
    expected_pages: list[dict[str, Any]],
    stored: bool,
) -> None:
    """Test the wizard pages list the entity ids of the entities they name."""
    mock_client.device_wizard = AsyncMock(**device_wizard)
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        device_capabilities={"wizard": {"configured": True}},
    )

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_wizard",
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {"pages": expected_pages}

    await hass.config_entries.async_unload(device.entry.entry_id)
    await hass.async_block_till_done()
    data = hass_storage[f"{DOMAIN}.{device.entry.entry_id}"]["data"]
    assert ("device_wizard" in data) is stored


async def test_device_wizard_imports_off_event_loop(
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the first wizard can decode without importing zstd on the event loop."""
    original_import_module = importlib.import_module
    loop_thread_id = threading.get_ident()
    monkeypatch.delitem(sys.modules, "compression.zstd", raising=False)

    def checked_import_module(name: str, package: str | None = None) -> ModuleType:
        assert (
            name != "compression.zstd"
            or name in sys.modules
            or threading.get_ident() != loop_thread_id
        )
        return original_import_module(name, package)

    wizard_import_module = Mock(wraps=checked_import_module)

    async def device_wizard() -> DeviceWizard:
        with patch.object(importlib, "import_module", wizard_import_module):
            # Zstandard-compressed {"version": 1, "pages": []}.
            return DeviceWizard.from_compressed_json(
                bytes.fromhex(
                    "28b52ffd2018c100007b2276657273696f6e223a312c227061676573223a5b5d7d"
                )
            )

    monkeypatch.setattr(importlib, "import_module", checked_import_module)
    mock_client.device_wizard = AsyncMock(side_effect=device_wizard)
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities={"wizard": {"configured": True}},
    )

    # Remove the preload if aioesphomeapi stops importing this during decoding.
    wizard_import_module.assert_any_call("compression.zstd")
    assert device.entry.runtime_data.device_wizard == DeviceWizard(pages=[])


async def test_get_device_wizard_not_configured(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test a device without a wizard is not asked for one."""
    mock_client.device_wizard = AsyncMock()
    device = await mock_esphome_device(mock_client=mock_client)

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_wizard",
            DEVICE_ID: _device_id_for_mac(device_registry, device.entry),
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {"pages": []}
    mock_client.device_wizard.assert_not_awaited()


@pytest.mark.parametrize(
    ("device_capabilities", "device_wizard", "expected_pages", "disconnects"),
    [
        # The device reports no wizard, for example after a firmware update
        pytest.param({}, {}, [], 0, id="no_wizard"),
        # The connection error aborts the connect, so the restored wizard stays
        pytest.param(
            {"wizard": {"configured": True}},
            {"side_effect": APIConnectionError},
            WIZARD_PAGES,
            1,
            id="fetch_failed",
        ),
    ],
)
async def test_get_device_wizard_restored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_client: APIClient,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
    device_capabilities: dict[str, Any],
    device_wizard: dict[str, Any],
    expected_pages: list[dict[str, Any]],
    disconnects: int,
) -> None:
    """Test the restored wizard is kept until a completed connect replaces it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        unique_id="11:22:33:44:55:aa",
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
    )
    entry.add_to_hass(hass)
    device_info = DeviceInfo(
        name="test", friendly_name="Test", mac_address="11:22:33:44:55:AA"
    )
    storage_key = f"{DOMAIN}.{entry.entry_id}"
    hass_storage[storage_key] = {
        "version": 1,
        "minor_version": 1,
        "key": storage_key,
        "data": {
            "device_info": device_info.to_dict(),
            "api_version": APIVersion(1, 19).to_dict(),
            "device_wizard": DeviceWizard.from_dict(WIZARD).to_dict(),
            "switch": [info.to_dict() for info in WIZARD_SWITCHES],
        },
    }
    connect_event = asyncio.Event()

    async def _blocked_connect() -> tuple[DeviceInfo, list[Any], list[Any]]:
        await connect_event.wait()
        return (device_info, WIZARD_SWITCHES, [])

    mock_client.device_info_and_list_entities = _blocked_connect
    mock_client.device_capabilities_compat = AsyncMock(
        return_value=DeviceCapabilities.from_dict(device_capabilities)
    )
    mock_client.device_wizard = AsyncMock(**device_wizard)
    assert await hass.config_entries.async_setup(entry.entry_id)

    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_wizard",
            DEVICE_ID: _device_id_for_mac(device_registry, entry),
        }
    )

    response = await websocket_client.receive_json()
    assert response["success"] is True
    assert response["result"] == {"pages": WIZARD_PAGES}

    connect_event.set()
    await hass.async_block_till_done()
    await websocket_client.send_json_auto_id(
        {
            TYPE: "esphome/get_device_wizard",
            DEVICE_ID: _device_id_for_mac(device_registry, entry),
        }
    )
    response = await websocket_client.receive_json()
    assert response["result"] == {"pages": expected_pages}
    assert mock_client.disconnect.await_count == disconnects


SENDSPIN_CLIENT_ID = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
SENDSPIN_TOKEN = "SP:1AAAQEAYEAUDAOCAJBIFQYDIOB4IBCEQTCQKRMFYYDENBWHA5DYPSA"


def _sendspin_capabilities(
    *, supported: bool = True, client_id: str = SENDSPIN_CLIENT_ID
) -> dict[str, Any]:
    """Return device capabilities for a device with (or without) Sendspin."""
    if not supported:
        return {}
    return {
        "sendspin": {
            "feature_flags": SendspinFeature.PAIRING_TOKEN,
            "client_id": client_id,
        }
    }


def _mock_sendspin_pairing_token(
    mock_client: APIClient,
    *,
    status: SendspinPairingTokenStatus | None = SendspinPairingTokenStatus.OK,
    token: str = SENDSPIN_TOKEN,
) -> None:
    """Make the mock device answer the pairing token request."""
    mock_client.sendspin_pairing_token = AsyncMock(
        return_value=SendspinPairingTokenResponse(status=status, token=token)
    )


async def _get_sendspin_pairing_token(
    hass_ws_client: WebSocketGenerator, client_id: str = SENDSPIN_CLIENT_ID
) -> dict[str, Any]:
    """Ask for the pairing token of a Sendspin client id."""
    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id(
        {TYPE: "sendspin/get_pairing_token", CLIENT_ID: client_id}
    )
    return await websocket_client.receive_json()


async def _subscribe_sendspin_clients(
    hass_ws_client: WebSocketGenerator,
) -> tuple[MockHAClientWebSocket, list[str]]:
    """Subscribe to the Sendspin client ids and return the first snapshot."""
    websocket_client = await hass_ws_client()
    await websocket_client.send_json_auto_id({TYPE: "sendspin/subscribe_clients"})
    response = await websocket_client.receive_json()
    assert response["success"] is True
    return websocket_client, await _receive_sendspin_clients(websocket_client)


async def _receive_sendspin_clients(
    websocket_client: MockHAClientWebSocket,
) -> list[str]:
    """Receive the next client id snapshot."""
    message = await websocket_client.receive_json()
    assert message["type"] == "event"
    return message["event"][CLIENT_IDS]


async def _assert_nothing_received(websocket_client: MockHAClientWebSocket) -> None:
    """Check that no event is pending by making a round trip to the server."""
    await websocket_client.send_json_auto_id({TYPE: "ping"})
    assert (await websocket_client.receive_json())["type"] == "pong"


async def _retry_client_id_fetch(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delay: float
) -> None:
    """Let the capabilities fetch scheduled after this delay run."""
    freezer.tick(delay + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_get_sendspin_pairing_token(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The token of the device whose client id matches is returned."""
    await mock_esphome_device(
        mock_client=mock_client, device_capabilities=_sendspin_capabilities()
    )
    _mock_sendspin_pairing_token(mock_client)

    for _ in range(2):
        response = await _get_sendspin_pairing_token(hass_ws_client)
        assert response["success"] is True
        assert response["result"] == {"token": SENDSPIN_TOKEN}
    # The client id comes from the capabilities fetched on connect
    assert mock_client.device_capabilities_compat.await_count == 1
    assert mock_client.sendspin_pairing_token.await_count == 2


@pytest.mark.parametrize(
    "device_capabilities",
    [
        pytest.param(_sendspin_capabilities(supported=False), id="no_sendspin"),
        pytest.param(_sendspin_capabilities(), id="other_client_id"),
        pytest.param(_sendspin_capabilities(client_id=""), id="client_id_unknown"),
    ],
)
async def test_get_sendspin_pairing_token_not_found(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    device_capabilities: dict[str, Any],
) -> None:
    """A client id no connected device is known to carry is not found."""
    await mock_esphome_device(
        mock_client=mock_client, device_capabilities=device_capabilities
    )
    _mock_sendspin_pairing_token(mock_client)

    response = await _get_sendspin_pairing_token(hass_ws_client, "other-client")
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    mock_client.sendspin_pairing_token.assert_not_awaited()


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (SendspinPairingTokenStatus.NOT_READY, "not ready"),
        (SendspinPairingTokenStatus.ENCRYPTION_REQUIRED, "encryption required"),
        (SendspinPairingTokenStatus.DISABLED, "disabled"),
        (SendspinPairingTokenStatus.FAILED, "failed"),
        pytest.param(None, "unknown status", id="unknown_status"),
    ],
)
async def test_get_sendspin_pairing_token_status_without_token(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    status: SendspinPairingTokenStatus | None,
    reason: str,
) -> None:
    """A matched device that hands out no token is an error that says why."""
    await mock_esphome_device(
        mock_client=mock_client, device_capabilities=_sendspin_capabilities()
    )
    _mock_sendspin_pairing_token(mock_client, status=status, token="")

    response = await _get_sendspin_pairing_token(hass_ws_client)
    assert response["success"] is False
    assert response["error"]["code"] == "unknown_error"
    assert response["error"]["message"] == f"test hands out no pairing token: {reason}"


async def test_get_sendspin_pairing_token_connection_error(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A device that fails to answer is reported as an error."""
    await mock_esphome_device(
        mock_client=mock_client, device_capabilities=_sendspin_capabilities()
    )
    mock_client.sendspin_pairing_token = AsyncMock(
        side_effect=APIConnectionError("boom")
    )

    response = await _get_sendspin_pairing_token(hass_ws_client)
    assert response["success"] is False
    assert response["error"]["code"] == "unknown_error"
    assert "boom" in response["error"]["message"]


async def test_get_sendspin_pairing_token_unavailable_device(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A disconnected device is not asked, even though its capabilities are kept."""
    device = await mock_esphome_device(
        mock_client=mock_client, device_capabilities=_sendspin_capabilities()
    )
    _mock_sendspin_pairing_token(mock_client)
    await device.mock_disconnect(False)

    response = await _get_sendspin_pairing_token(hass_ws_client)
    assert response["success"] is False
    assert response["error"]["code"] == "not_found"
    mock_client.sendspin_pairing_token.assert_not_awaited()


async def test_subscribe_sendspin_clients(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The client ids are sent on subscribe and whenever a device comes or goes."""
    device = await mock_esphome_device(
        mock_client=mock_client, device_capabilities=_sendspin_capabilities()
    )
    websocket_client, client_ids = await _subscribe_sendspin_clients(hass_ws_client)
    assert client_ids == [SENDSPIN_CLIENT_ID]

    await device.mock_disconnect(False)
    assert await _receive_sendspin_clients(websocket_client) == []

    await device.mock_connect()
    assert await _receive_sendspin_clients(websocket_client) == [SENDSPIN_CLIENT_ID]
    await _assert_nothing_received(websocket_client)


@pytest.mark.parametrize(
    "device_capabilities",
    [
        pytest.param(_sendspin_capabilities(supported=False), id="no_sendspin"),
        pytest.param(_sendspin_capabilities(client_id=""), id="client_id_unknown"),
    ],
)
async def test_subscribe_sendspin_clients_without_client_ids(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    device_capabilities: dict[str, Any],
) -> None:
    """A device without a known client id is not announced."""
    device = await mock_esphome_device(
        mock_client=mock_client, device_capabilities=device_capabilities
    )
    websocket_client, client_ids = await _subscribe_sendspin_clients(hass_ws_client)
    assert client_ids == []

    await device.mock_disconnect(False)
    await _assert_nothing_received(websocket_client)


async def test_subscribe_sendspin_clients_unsubscribe(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """After unsubscribing no more snapshots arrive."""
    device = await mock_esphome_device(
        mock_client=mock_client, device_capabilities=_sendspin_capabilities()
    )
    websocket_client, _ = await _subscribe_sendspin_clients(hass_ws_client)
    await websocket_client.send_json_auto_id(
        {TYPE: "unsubscribe_events", "subscription": 1}
    )
    assert (await websocket_client.receive_json())["success"] is True

    await device.mock_disconnect(False)
    await _assert_nothing_received(websocket_client)


def _mock_client_id_refresh(mock_client: APIClient, **kwargs: Any) -> AsyncMock:
    """Make the mock device answer the capabilities request a refresh sends.

    A refresh asks a device that reported Sendspin, so it skips the compat path
    the connect-time request uses.
    """
    mock_client.device_capabilities = AsyncMock(**kwargs)
    return mock_client.device_capabilities


async def test_subscribe_sendspin_clients_client_id_learned_later(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    """A device whose Sendspin client had not started on connect is asked again."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities=_sendspin_capabilities(client_id=""),
    )
    _mock_sendspin_pairing_token(mock_client)
    websocket_client, client_ids = await _subscribe_sendspin_clients(hass_ws_client)
    assert client_ids == []

    # Still not started: asked again later, with a growing delay
    refresh = _mock_client_id_refresh(
        mock_client,
        return_value=DeviceCapabilities.from_dict(_sendspin_capabilities(client_id="")),
    )
    await _retry_client_id_fetch(hass, freezer, 5)
    assert refresh.await_count == 1
    await _assert_nothing_received(websocket_client)

    refresh.return_value = DeviceCapabilities.from_dict(_sendspin_capabilities())
    await _retry_client_id_fetch(hass, freezer, 10)
    assert refresh.await_count == 2
    assert await _receive_sendspin_clients(websocket_client) == [SENDSPIN_CLIENT_ID]

    response = await _get_sendspin_pairing_token(hass_ws_client)
    assert response["result"] == {"token": SENDSPIN_TOKEN}
    capabilities = device.entry.runtime_data.device_capabilities
    assert capabilities.sendspin.client_id == SENDSPIN_CLIENT_ID

    # Once known, the device is left alone; the refreshed capabilities are saved
    await _retry_client_id_fetch(hass, freezer, 300)
    assert refresh.await_count == 2
    assert mock_client.device_capabilities_compat.await_count == 1
    stored = hass_storage[f"{DOMAIN}.{device.entry.entry_id}"]["data"]
    assert stored["device_capabilities"] == capabilities.to_dict()


async def test_subscribe_sendspin_clients_client_id_refresh_stops(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A disconnected device is not asked again; a connected one that fails is."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities=_sendspin_capabilities(client_id=""),
    )
    websocket_client, _ = await _subscribe_sendspin_clients(hass_ws_client)

    refresh = _mock_client_id_refresh(
        mock_client, side_effect=APIConnectionError("boom")
    )
    await device.mock_disconnect(False)
    await _retry_client_id_fetch(hass, freezer, 5)
    refresh.assert_not_awaited()

    await device.mock_connect()
    assert mock_client.device_capabilities_compat.await_count == 2
    # A request that times out while connected is retried with a longer delay
    await _retry_client_id_fetch(hass, freezer, 5)
    assert refresh.await_count == 1
    await _retry_client_id_fetch(hass, freezer, 10)
    assert refresh.await_count == 2
    await _assert_nothing_received(websocket_client)

    refresh.side_effect = None
    refresh.return_value = DeviceCapabilities.from_dict(_sendspin_capabilities())
    await _retry_client_id_fetch(hass, freezer, 20)
    assert await _receive_sendspin_clients(websocket_client) == [SENDSPIN_CLIENT_ID]


async def test_subscribe_sendspin_clients_refresh_survives_capabilities_update(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A cache update in the same connection, like a Z-Wave home id, is kept by the refresh."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities=_sendspin_capabilities(client_id=""),
    )
    websocket_client, _ = await _subscribe_sendspin_clients(hass_ws_client)

    fetch_started = asyncio.Event()
    release_fetch = asyncio.Event()

    async def _slow_fetch() -> DeviceCapabilities:
        fetch_started.set()
        await release_fetch.wait()
        return DeviceCapabilities.from_dict(_sendspin_capabilities())

    _mock_client_id_refresh(mock_client, side_effect=_slow_fetch)
    freezer.tick(6)
    async_fire_time_changed(hass)
    await fetch_started.wait()

    # The device reports a new Z-Wave home id while the request is out
    entry_data = device.entry.runtime_data
    updated = entry_data.device_capabilities.to_dict()
    updated["zwave_proxy"]["home_id"] = 3551671779
    entry_data.device_capabilities = DeviceCapabilities.from_dict(updated)
    release_fetch.set()
    await hass.async_block_till_done()
    assert await _receive_sendspin_clients(websocket_client) == [SENDSPIN_CLIENT_ID]
    capabilities = entry_data.device_capabilities
    assert capabilities.sendspin.client_id == SENDSPIN_CLIENT_ID
    assert capabilities.zwave_proxy.home_id == 3551671779


async def test_subscribe_sendspin_clients_refresh_after_reconnect(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A refresh answered after the device reconnected does not clobber the new state."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_capabilities=_sendspin_capabilities(client_id=""),
    )
    websocket_client, _ = await _subscribe_sendspin_clients(hass_ws_client)

    fetch_started = asyncio.Event()
    release_fetch = asyncio.Event()
    stale_capabilities = DeviceCapabilities.from_dict(
        _sendspin_capabilities(client_id="stale")
    )

    async def _slow_fetch() -> DeviceCapabilities:
        fetch_started.set()
        await release_fetch.wait()
        return stale_capabilities

    _mock_client_id_refresh(mock_client, side_effect=_slow_fetch)
    freezer.tick(6)
    async_fire_time_changed(hass)
    await fetch_started.wait()

    # The device reconnects while the refresh is in flight
    mock_client.device_capabilities_compat.return_value = DeviceCapabilities.from_dict(
        _sendspin_capabilities()
    )
    await device.mock_disconnect(False)
    await device.mock_connect()
    assert await _receive_sendspin_clients(websocket_client) == [SENDSPIN_CLIENT_ID]

    release_fetch.set()
    await hass.async_block_till_done()
    assert device.entry.runtime_data.device_capabilities.sendspin.client_id == (
        SENDSPIN_CLIENT_ID
    )
    await _assert_nothing_received(websocket_client)
