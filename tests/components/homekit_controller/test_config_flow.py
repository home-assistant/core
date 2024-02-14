"""Tests for homekit_controller config flow."""
import asyncio
from ipaddress import ip_address
import unittest.mock
from unittest.mock import AsyncMock, patch

import aiohomekit
from aiohomekit.exceptions import AuthenticationError
from aiohomekit.model import Accessories, Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
from bleak.exc import BleakError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.homekit_controller import config_flow
from homeassistant.components.homekit_controller.const import KNOWN_DEVICES
from homeassistant.components.homekit_controller.storage import async_get_entity_storage
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

PAIRING_START_FORM_ERRORS = [
    (KeyError, "pairing_failed"),
]

PAIRING_START_ABORT_ERRORS = [
    (aiohomekit.AccessoryNotFoundError, "accessory_not_found_error"),
    (aiohomekit.UnavailableError, "already_paired"),
]

PAIRING_TRY_LATER_ERRORS = [
    (aiohomekit.BusyError, "busy_error"),
    (aiohomekit.MaxTriesError, "max_tries_error"),
    (IndexError, "protocol_error"),
]

PAIRING_FINISH_FORM_ERRORS = [
    (aiohomekit.exceptions.MalformedPinError, "authentication_error"),
    (aiohomekit.MaxPeersError, "max_peers_error"),
    (aiohomekit.AuthenticationError, "authentication_error"),
    (aiohomekit.UnknownError, "unknown_error"),
    (KeyError, "pairing_failed"),
]

PAIRING_FINISH_ABORT_ERRORS = [
    (aiohomekit.AccessoryNotFoundError, "accessory_not_found_error")
]


INSECURE_PAIRING_CODES = [
    "111-11-111",
    "123-45-678",
    "22222222",
    "111-11-111 ",
    " 111-11-111",
]


INVALID_PAIRING_CODES = [
    "aaa-aa-aaa",
    "aaa-11-aaa",
    "111-aa-aaa",
    "aaa-aa-111",
    "1111-1-111",
    "a111-11-111",
    "111-11-111a",
    "1111111",
]


VALID_PAIRING_CODES = [
    "114-11-111",
    "123-45-679",
    "123-45-679  ",
    "11121111",
    "98765432",
    "   98765432  ",
]

NOT_HK_BLUETOOTH_SERVICE_INFO = BluetoothServiceInfo(
    name="FakeAccessory",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-81,
    manufacturer_data={12: b"\x06\x12\x34"},
    service_data={},
    service_uuids=[],
    source="local",
)

HK_BLUETOOTH_SERVICE_INFO_NOT_DISCOVERED = BluetoothServiceInfo(
    name="Eve Energy Not Found",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-81,
    # ID is '9b:86:af:01:af:db'
    manufacturer_data={
        76: b"\x061\x01\x9b\x86\xaf\x01\xaf\xdb\x07\x00\x06\x00\x02\x02X\x19\xb1Q"
    },
    service_data={},
    service_uuids=[],
    source="local",
)

HK_BLUETOOTH_SERVICE_INFO_DISCOVERED_UNPAIRED = BluetoothServiceInfo(
    name="Eve Energy Found Unpaired",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-81,
    # ID is '00:00:00:00:00:00', pairing flag is byte 3
    manufacturer_data={
        76: b"\x061\x01\x00\x00\x00\x00\x00\x00\x07\x00\x06\x00\x02\x02X\x19\xb1Q"
    },
    service_data={},
    service_uuids=[],
    source="local",
)


HK_BLUETOOTH_SERVICE_INFO_DISCOVERED_PAIRED = BluetoothServiceInfo(
    name="Eve Energy Found Paired",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-81,
    # ID is '00:00:00:00:00:00', pairing flag is byte 3
    manufacturer_data={
        76: b"\x061\x00\x00\x00\x00\x00\x00\x00\x07\x00\x06\x00\x02\x02X\x19\xb1Q"
    },
    service_data={},
    service_uuids=[],
    source="local",
)


@pytest.mark.parametrize("pairing_code", INVALID_PAIRING_CODES)
def test_invalid_pairing_codes(pairing_code) -> None:
    """Test ensure_pin_format raises for an invalid pin code."""
    with pytest.raises(aiohomekit.exceptions.MalformedPinError):
        config_flow.ensure_pin_format(pairing_code)


@pytest.mark.parametrize("pairing_code", INSECURE_PAIRING_CODES)
def test_insecure_pairing_codes(pairing_code) -> None:
    """Test ensure_pin_format raises for an invalid setup code."""
    with pytest.raises(config_flow.InsecureSetupCode):
        config_flow.ensure_pin_format(pairing_code)

    config_flow.ensure_pin_format(pairing_code, allow_insecure_setup_codes=True)


@pytest.mark.parametrize("pairing_code", VALID_PAIRING_CODES)
def test_valid_pairing_codes(pairing_code) -> None:
    """Test ensure_pin_format corrects format for a valid pin in an alternative format."""
    valid_pin = config_flow.ensure_pin_format(pairing_code).split("-")
    assert len(valid_pin) == 3
    assert len(valid_pin[0]) == 3
    assert len(valid_pin[1]) == 2
    assert len(valid_pin[2]) == 3


def get_flow_context(hass, result):
    """Get the flow context from the result of async_init or async_configure."""
    flow = next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )

    return flow["context"]


def get_device_discovery_info(
    device, upper_case_props=False, missing_csharp=False, paired=False
) -> zeroconf.ZeroconfServiceInfo:
    """Turn a aiohomekit format zeroconf entry into a homeassistant one."""
    result = zeroconf.ZeroconfServiceInfo(
        ip_address=ip_address("127.0.0.1"),
        ip_addresses=[ip_address("127.0.0.1")],
        hostname=device.description.name,
        name=device.description.name + "._hap._tcp.local.",
        port=8080,
        properties={
            "md": device.description.model,
            "pv": "1.0",
            zeroconf.ATTR_PROPERTIES_ID: device.description.id,
            "c#": device.description.config_num,
            "s#": device.description.state_num,
            "ff": "0",
            "ci": "7",
            "sf": "0" if paired else "1",
            "sh": "",
        },
        type="_hap._tcp.local.",
    )

    if missing_csharp:
        del result.properties["c#"]

    if upper_case_props:
        result.properties = {
            key.upper(): val for (key, val) in result.properties.items()
        }

    return result


def setup_mock_accessory(controller):
    """Add a bridge accessory to a test controller."""
    bridge = Accessories()

    accessory = Accessory.create_with_info(
        name="Koogeek-LS1-20833F",
        manufacturer="Koogeek",
        model="LS1",
        serial_number="12345",
        firmware_revision="1.1",
    )
    accessory.aid = 1

    service = accessory.add_service(ServicesTypes.LIGHTBULB)
    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = 0

    bridge.add_accessory(accessory)

    return controller.add_device(bridge)


@pytest.mark.parametrize("upper_case_props", [True, False])
@pytest.mark.parametrize("missing_csharp", [True, False])
async def test_discovery_works(
    hass: HomeAssistant, controller, upper_case_props, missing_csharp
) -> None:
    """Test a device being discovered."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device, upper_case_props, missing_csharp)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert get_flow_context(hass, result) == {
        "source": config_entries.SOURCE_ZEROCONF,
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device enters pairing mode and displays code
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    # Pairing doesn't error error and pairing results
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == {}


async def test_abort_duplicate_flow(hass: HomeAssistant, controller) -> None:
    """Already paired."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_pair_already_paired_1(hass: HomeAssistant, controller) -> None:
    """Already paired."""
    device = setup_mock_accessory(controller)
    # Flag device as already paired
    discovery_info = get_device_discovery_info(device, paired=True)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_paired"


async def test_unknown_domain_type(hass: HomeAssistant, controller) -> None:
    """Test that aiohomekit can reject discoveries it doesn't support."""
    device = setup_mock_accessory(controller)
    # Flag device as already paired
    discovery_info = get_device_discovery_info(device)
    discovery_info.name = "TestDevice._music._tap.local."

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "ignored_model"


async def test_id_missing(hass: HomeAssistant, controller) -> None:
    """Test id is missing."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Remove id from device
    del discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID]

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "invalid_properties"


async def test_discovery_ignored_model(hass: HomeAssistant, controller) -> None:
    """Already paired."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)
    discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID] = "AA:BB:CC:DD:EE:FF"
    discovery_info.properties["md"] = "HHKBridge1,1"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "ignored_model"


async def test_discovery_ignored_hk_bridge(
    hass: HomeAssistant, controller, device_registry: dr.DeviceRegistry
) -> None:
    """Ensure we ignore homekit bridges and accessories created by the homekit integration."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    config_entry = MockConfigEntry(domain=config_flow.HOMEKIT_BRIDGE_DOMAIN, data={})
    config_entry.add_to_hass(hass)
    formatted_mac = dr.format_mac("AA:BB:CC:DD:EE:FF")

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, formatted_mac)},
    )

    discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID] = "AA:BB:CC:DD:EE:FF"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "ignored_model"


async def test_discovery_does_not_ignore_non_homekit(
    hass: HomeAssistant, controller, device_registry: dr.DeviceRegistry
) -> None:
    """Do not ignore devices that are not from the homekit integration."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    config_entry = MockConfigEntry(domain="not_homekit", data={})
    config_entry.add_to_hass(hass)
    formatted_mac = dr.format_mac("AA:BB:CC:DD:EE:FF")

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, formatted_mac)},
    )

    discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID] = "AA:BB:CC:DD:EE:FF"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "form"


async def test_discovery_broken_pairing_flag(hass: HomeAssistant, controller) -> None:
    """There is already a config entry for the pairing and its pairing flag is wrong in zeroconf.

    We have seen this particular implementation error in 2 different devices.
    """
    await controller.add_paired_device(Accessories(), "00:00:00:00:00:00")

    MockConfigEntry(
        domain="homekit_controller",
        data={"AccessoryPairingID": "00:00:00:00:00:00"},
        unique_id="00:00:00:00:00:00",
    ).add_to_hass(hass)

    # We just added a mock config entry so it must be visible in hass
    assert len(hass.config_entries.async_entries()) == 1

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Make sure that we are pairable
    assert discovery_info.properties["sf"] != 0x0

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should still be paired.
    config_entry_count = len(hass.config_entries.async_entries())
    assert config_entry_count == 1

    # Even though discovered as pairable, we bail out as already paired.
    assert result["reason"] == "already_paired"


async def test_discovery_invalid_config_entry(hass: HomeAssistant, controller) -> None:
    """There is already a config entry for the pairing id but it's invalid."""
    pairing = await controller.add_paired_device(Accessories(), "00:00:00:00:00:00")

    MockConfigEntry(
        domain="homekit_controller",
        data={"AccessoryPairingID": "00:00:00:00:00:00"},
        unique_id="00:00:00:00:00:00",
    ).add_to_hass(hass)

    # We just added a mock config entry so it must be visible in hass
    assert len(hass.config_entries.async_entries()) == 1

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    with patch.object(
        pairing,
        "list_accessories_and_characteristics",
        side_effect=AuthenticationError("Invalid pairing keys"),
    ):
        result = await hass.config_entries.flow.async_init(
            "homekit_controller",
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

    # Discovery of a HKID that is in a pairable state but for which there is
    # already a config entry - in that case the stale config entry is
    # automatically removed.
    config_entry_count = len(hass.config_entries.async_entries())
    assert config_entry_count == 0

    # And new config flow should continue allowing user to set up a new pairing
    assert result["type"] == "form"


async def test_discovery_ignored_config_entry(hass: HomeAssistant, controller) -> None:
    """There is already a config entry but it is ignored."""
    pairing = await controller.add_paired_device(Accessories(), "00:00:00:00:00:00")

    MockConfigEntry(
        domain="homekit_controller",
        data={},
        unique_id="00:00:00:00:00:00",
        source=config_entries.SOURCE_IGNORE,
    ).add_to_hass(hass)

    # We just added a mock config entry so it must be visible in hass
    assert len(hass.config_entries.async_entries()) == 1

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    with patch.object(
        pairing,
        "list_accessories_and_characteristics",
        side_effect=AuthenticationError("Invalid pairing keys"),
    ):
        result = await hass.config_entries.flow.async_init(
            "homekit_controller",
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

    # Entry is still ignored
    config_entry_count = len(hass.config_entries.async_entries())
    assert config_entry_count == 1

    # We should abort since there is no accessory id in the data
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_already_configured(hass: HomeAssistant, controller) -> None:
    """Already configured."""
    entry = MockConfigEntry(
        domain="homekit_controller",
        data={
            "AccessoryIP": "4.4.4.4",
            "AccessoryPort": 66,
            "AccessoryPairingID": "00:00:00:00:00:00",
        },
        unique_id="00:00:00:00:00:00",
    )
    entry.add_to_hass(hass)

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Set device as already paired
    discovery_info.properties["sf"] = 0x00

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data["AccessoryIP"] == discovery_info.host
    assert entry.data["AccessoryPort"] == discovery_info.port


async def test_discovery_already_configured_update_csharp(
    hass: HomeAssistant, controller
) -> None:
    """Already configured and csharp changes."""
    entry = MockConfigEntry(
        domain="homekit_controller",
        data={
            "AccessoryIP": "4.4.4.4",
            "AccessoryPort": 66,
            "AccessoryPairingID": "AA:BB:CC:DD:EE:FF",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    connection_mock = AsyncMock()
    hass.data[KNOWN_DEVICES] = {"AA:BB:CC:DD:EE:FF": connection_mock}

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Set device as already paired
    discovery_info.properties["sf"] = 0x00
    discovery_info.properties["c#"] = 99999
    discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID] = "AA:BB:CC:DD:EE:FF"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert entry.data["AccessoryIP"] == discovery_info.host
    assert entry.data["AccessoryPort"] == discovery_info.port


@pytest.mark.parametrize(("exception", "expected"), PAIRING_START_ABORT_ERRORS)
async def test_pair_abort_errors_on_start(
    hass: HomeAssistant, controller, exception, expected
) -> None:
    """Test various pairing errors."""

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # User initiates pairing - device refuses to enter pairing mode
    test_exc = exception("error")
    with patch.object(device, "async_start_pairing", side_effect=test_exc):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "abort"
    assert result["reason"] == expected


@pytest.mark.parametrize(("exception", "expected"), PAIRING_TRY_LATER_ERRORS)
async def test_pair_try_later_errors_on_start(
    hass: HomeAssistant, controller, exception, expected
) -> None:
    """Test various pairing errors."""

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # User initiates pairing - device refuses to enter pairing mode but may be successful after entering pairing mode or rebooting
    test_exc = exception("error")
    with patch.object(device, "async_start_pairing", side_effect=test_exc):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["step_id"] == expected
    assert result2["type"] == "form"

    # Device is rebooted or placed into pairing mode as they have been instructed

    # We start pairing again
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input={"any": "key"}
    )

    # .. and successfully complete pair
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"], user_input={"pairing_code": "111-22-333"}
    )

    assert result4["type"] == "create_entry"
    assert result4["title"] == "Koogeek-LS1-20833F"


@pytest.mark.parametrize(("exception", "expected"), PAIRING_START_FORM_ERRORS)
async def test_pair_form_errors_on_start(
    hass: HomeAssistant, controller, exception, expected
) -> None:
    """Test various pairing errors."""

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User initiates pairing - device refuses to enter pairing mode
    test_exc = exception("error")
    with patch.object(device, "async_start_pairing", side_effect=test_exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"pairing_code": "111-22-333"}
        )
    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == expected

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User gets back the form
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "form"
    assert result["errors"] == {}

    # User re-tries entering pairing code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"


@pytest.mark.parametrize(("exception", "expected"), PAIRING_FINISH_ABORT_ERRORS)
async def test_pair_abort_errors_on_finish(
    hass: HomeAssistant, controller, exception, expected
) -> None:
    """Test various pairing errors."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User initiates pairing - this triggers the device to show a pairing code
    # and then HA to show a pairing form
    finish_pairing = unittest.mock.AsyncMock(side_effect=exception("error"))
    with patch.object(device, "async_start_pairing", return_value=finish_pairing):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "form"
    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User enters pairing code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == expected


@pytest.mark.parametrize(("exception", "expected"), PAIRING_FINISH_FORM_ERRORS)
async def test_pair_form_errors_on_finish(
    hass: HomeAssistant, controller, exception, expected
) -> None:
    """Test various pairing errors."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User initiates pairing - this triggers the device to show a pairing code
    # and then HA to show a pairing form
    finish_pairing = unittest.mock.AsyncMock(side_effect=exception("error"))
    with patch.object(device, "async_start_pairing", return_value=finish_pairing):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "form"
    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User enters pairing code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == expected

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
        "pairing": True,
    }


async def test_pair_unknown_errors(hass: HomeAssistant, controller) -> None:
    """Test describing unknown errors."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User initiates pairing - this triggers the device to show a pairing code
    # and then HA to show a pairing form
    finish_pairing = unittest.mock.AsyncMock(
        side_effect=BleakError("The bluetooth connection failed")
    )
    with patch.object(device, "async_start_pairing", return_value=finish_pairing):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "form"
    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User enters pairing code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == "pairing_failed"
    assert (
        result["description_placeholders"]["error"] == "The bluetooth connection failed"
    )

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
        "pairing": True,
    }


async def test_user_works(hass: HomeAssistant, controller) -> None:
    """Test user initiated disovers devices."""
    setup_mock_accessory(controller)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert get_flow_context(hass, result) == {
        "source": config_entries.SOURCE_USER,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device": "TestDevice"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    assert get_flow_context(hass, result) == {
        "source": config_entries.SOURCE_USER,
        "unique_id": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice", "category": "Other"},
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"


async def test_user_pairing_with_insecure_setup_code(
    hass: HomeAssistant, controller
) -> None:
    """Test user initiated disovers devices."""
    device = setup_mock_accessory(controller)
    device.pairing_code = "123-45-678"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert get_flow_context(hass, result) == {
        "source": config_entries.SOURCE_USER,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device": "TestDevice"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    assert get_flow_context(hass, result) == {
        "source": config_entries.SOURCE_USER,
        "unique_id": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice", "category": "Other"},
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "123-45-678"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert result["errors"] == {"pairing_code": "insecure_setup_code"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"pairing_code": "123-45-678", "allow_insecure_setup_codes": True},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"


async def test_user_no_devices(hass: HomeAssistant, controller) -> None:
    """Test user initiated pairing where no devices discovered."""
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"


async def test_user_no_unpaired_devices(hass: HomeAssistant, controller) -> None:
    """Test user initiated pairing where no unpaired devices discovered."""
    device = setup_mock_accessory(controller)

    # Pair the mock device so that it shows as paired in discovery
    finish_pairing = await device.async_start_pairing(device.description.id)
    await finish_pairing(device.pairing_code)

    # Device discovery is requested
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"


async def test_unignore_works(hass: HomeAssistant, controller) -> None:
    """Test rediscovery triggered disovers work."""
    device = setup_mock_accessory(controller)

    # Device is unignored
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_UNIGNORE},
        data={"unique_id": device.description.id},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Other"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_UNIGNORE,
    }

    # User initiates pairing by clicking on 'configure' - device enters pairing mode and displays code
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    # Pairing finalized
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"


async def test_unignore_ignores_missing_devices(
    hass: HomeAssistant, controller
) -> None:
    """Test rediscovery triggered disovers handle devices that have gone away."""
    setup_mock_accessory(controller)

    # Device is unignored
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_UNIGNORE},
        data={"unique_id": "00:00:00:00:00:01"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "accessory_not_found_error"


async def test_discovery_dismiss_existing_flow_on_paired(
    hass: HomeAssistant, controller
) -> None:
    """Test that existing flows get dismissed once paired to something else."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Set device as already not paired
    discovery_info.properties["sf"] = 0x01
    discovery_info.properties["c#"] = 99999
    discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID] = "AA:BB:CC:DD:EE:FF"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    await hass.async_block_till_done()
    assert (
        len(hass.config_entries.flow.async_progress_by_handler("homekit_controller"))
        == 1
    )

    # Set device as already paired
    discovery_info.properties["sf"] = 0x00
    # Device is discovered again after pairing to someone else
    result2 = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "already_paired"
    await hass.async_block_till_done()
    assert (
        len(hass.config_entries.flow.async_progress_by_handler("homekit_controller"))
        == 0
    )


async def test_mdns_update_to_paired_during_pairing(
    hass: HomeAssistant, controller
) -> None:
    """Test we do not abort pairing if mdns is updated to reflect paired during pairing."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)
    discovery_info_paired = get_device_discovery_info(device, paired=True)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    mdns_update_to_paired = asyncio.Event()

    original_async_start_pairing = device.async_start_pairing

    async def _async_start_pairing(*args, **kwargs):
        finish_pairing = await original_async_start_pairing(*args, **kwargs)

        async def _finish_pairing(*args, **kwargs):
            # Insert an event wait to make sure
            # we trigger the mdns update in the middle of the pairing
            await mdns_update_to_paired.wait()
            return await finish_pairing(*args, **kwargs)

        return _finish_pairing

    with patch.object(device, "async_start_pairing", _async_start_pairing):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "form"
    assert get_flow_context(hass, result) == {
        "title_placeholders": {"name": "TestDevice", "category": "Outlet"},
        "unique_id": "00:00:00:00:00:00",
        "source": config_entries.SOURCE_ZEROCONF,
    }

    # User enters pairing code
    task = asyncio.create_task(
        hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"pairing_code": "111-22-333"}
        )
    )
    # Make sure when the device is discovered as paired via mdns
    # it does not abort pairing if it happens before pairing is finished
    result2 = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info_paired,
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_paired"
    mdns_update_to_paired.set()
    result = await task
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == {}


async def test_discovery_no_bluetooth_support(hass: HomeAssistant, controller) -> None:
    """Test discovery with bluetooth support not available."""
    with patch(
        "homeassistant.components.homekit_controller.config_flow.aiohomekit_const.BLE_TRANSPORT_SUPPORTED",
        False,
    ):
        result = await hass.config_entries.flow.async_init(
            "homekit_controller",
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=HK_BLUETOOTH_SERVICE_INFO_NOT_DISCOVERED,
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "ignored_model"


async def test_bluetooth_not_homekit(hass: HomeAssistant, controller) -> None:
    """Test bluetooth discovery with a non-homekit device."""
    with patch(
        "homeassistant.components.homekit_controller.config_flow.aiohomekit_const.BLE_TRANSPORT_SUPPORTED",
        True,
    ):
        result = await hass.config_entries.flow.async_init(
            "homekit_controller",
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=NOT_HK_BLUETOOTH_SERVICE_INFO,
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "ignored_model"


async def test_bluetooth_valid_device_no_discovery(
    hass: HomeAssistant, controller
) -> None:
    """Test bluetooth discovery  with a homekit device and discovery fails."""
    with patch(
        "homeassistant.components.homekit_controller.config_flow.aiohomekit_const.BLE_TRANSPORT_SUPPORTED",
        True,
    ):
        result = await hass.config_entries.flow.async_init(
            "homekit_controller",
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=HK_BLUETOOTH_SERVICE_INFO_NOT_DISCOVERED,
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "accessory_not_found_error"


async def test_bluetooth_valid_device_discovery_paired(
    hass: HomeAssistant, controller
) -> None:
    """Test bluetooth discovery  with a homekit device and discovery works."""
    setup_mock_accessory(controller)

    with patch(
        "homeassistant.components.homekit_controller.config_flow.aiohomekit_const.BLE_TRANSPORT_SUPPORTED",
        True,
    ):
        result = await hass.config_entries.flow.async_init(
            "homekit_controller",
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=HK_BLUETOOTH_SERVICE_INFO_DISCOVERED_PAIRED,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_paired"


async def test_bluetooth_valid_device_discovery_unpaired(
    hass: HomeAssistant, controller
) -> None:
    """Test bluetooth discovery with a homekit device and discovery works."""
    setup_mock_accessory(controller)
    storage = await async_get_entity_storage(hass)

    with patch(
        "homeassistant.components.homekit_controller.config_flow.aiohomekit_const.BLE_TRANSPORT_SUPPORTED",
        True,
    ):
        result = await hass.config_entries.flow.async_init(
            "homekit_controller",
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=HK_BLUETOOTH_SERVICE_INFO_DISCOVERED_UNPAIRED,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert storage.get_map("00:00:00:00:00:00") is None

    assert get_flow_context(hass, result) == {
        "source": config_entries.SOURCE_BLUETOOTH,
        "unique_id": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice", "category": "Other"},
    }

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] == FlowResultType.FORM
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Koogeek-LS1-20833F"
    assert result3["data"] == {}

    assert storage.get_map("00:00:00:00:00:00") is not None


async def test_discovery_updates_ip_when_config_entry_set_up(
    hass: HomeAssistant, controller
) -> None:
    """Already configured updates ip when config entry set up."""
    entry = MockConfigEntry(
        domain="homekit_controller",
        data={
            "AccessoryIP": "4.4.4.4",
            "AccessoryPort": 66,
            "AccessoryPairingID": "AA:BB:CC:DD:EE:FF",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    connection_mock = AsyncMock()
    hass.data[KNOWN_DEVICES] = {"AA:BB:CC:DD:EE:FF": connection_mock}

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Set device as already paired
    discovery_info.properties["sf"] = 0x00
    discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID] = "Aa:bB:cC:dD:eE:fF"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert entry.data["AccessoryIP"] == discovery_info.host
    assert entry.data["AccessoryPort"] == discovery_info.port


async def test_discovery_updates_ip_config_entry_not_set_up(
    hass: HomeAssistant, controller
) -> None:
    """Already configured updates ip when the config entry is not set up."""
    entry = MockConfigEntry(
        domain="homekit_controller",
        data={
            "AccessoryIP": "4.4.4.4",
            "AccessoryPort": 66,
            "AccessoryPairingID": "AA:BB:CC:DD:EE:FF",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    AsyncMock()

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Set device as already paired
    discovery_info.properties["sf"] = 0x00
    discovery_info.properties[zeroconf.ATTR_PROPERTIES_ID] = "Aa:bB:cC:dD:eE:fF"

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert entry.data["AccessoryIP"] == discovery_info.host
    assert entry.data["AccessoryPort"] == discovery_info.port
