"""Tests for homekit_controller config flow."""
import json
from unittest import mock

import aiohomekit
from aiohomekit.model import Accessories, Accessory
from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import ServicesTypes
import asynctest
from asynctest import patch
import pytest

from homeassistant.components.homekit_controller import config_flow

from tests.common import MockConfigEntry
from tests.components.homekit_controller.common import setup_platform

PAIRING_START_FORM_ERRORS = [
    (aiohomekit.BusyError, "busy_error"),
    (aiohomekit.MaxTriesError, "max_tries_error"),
    (KeyError, "pairing_failed"),
]

PAIRING_START_ABORT_ERRORS = [
    (aiohomekit.AccessoryNotFoundError, "accessory_not_found_error"),
    (aiohomekit.UnavailableError, "already_paired"),
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

INVALID_PAIRING_CODES = [
    "aaa-aa-aaa",
    "aaa-11-aaa",
    "111-aa-aaa",
    "aaa-aa-111",
    "1111-1-111",
    "a111-11-111",
    " 111-11-111",
    "111-11-111 ",
    "111-11-111a",
    "1111111",
]


VALID_PAIRING_CODES = [
    "111-11-111",
    "123-45-678",
    "11111111",
    "98765432",
]


def _setup_flow_handler(hass, pairing=None):
    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass
    flow.context = {}

    finish_pairing = asynctest.CoroutineMock(return_value=pairing)

    discovery = mock.Mock()
    discovery.device_id = "00:00:00:00:00:00"
    discovery.start_pairing = asynctest.CoroutineMock(return_value=finish_pairing)

    flow.controller = mock.Mock()
    flow.controller.pairings = {}
    flow.controller.find_ip_by_device_id = asynctest.CoroutineMock(
        return_value=discovery
    )

    return flow


@pytest.mark.parametrize("pairing_code", INVALID_PAIRING_CODES)
def test_invalid_pairing_codes(pairing_code):
    """Test ensure_pin_format raises for an invalid pin code."""
    with pytest.raises(aiohomekit.exceptions.MalformedPinError):
        config_flow.ensure_pin_format(pairing_code)


@pytest.mark.parametrize("pairing_code", VALID_PAIRING_CODES)
def test_valid_pairing_codes(pairing_code):
    """Test ensure_pin_format corrects format for a valid pin in an alternative format."""
    valid_pin = config_flow.ensure_pin_format(pairing_code).split("-")
    assert len(valid_pin) == 3
    assert len(valid_pin[0]) == 3
    assert len(valid_pin[1]) == 2
    assert len(valid_pin[2]) == 3


def get_flow_context(hass, result):
    """Get the flow context from the result of async_init or async_configure."""
    flow = next(
        (
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
    )

    return flow["context"]


def get_device_discovery_info(device, upper_case_props=False, missing_csharp=False):
    """Turn a aiohomekit format zeroconf entry into a homeassistant one."""
    record = device.info
    result = {
        "host": record["address"],
        "port": record["port"],
        "hostname": record["name"],
        "type": "_hap._tcp.local.",
        "name": record["name"],
        "properties": {
            "md": record["md"],
            "pv": record["pv"],
            "id": device.device_id,
            "c#": record["c#"],
            "s#": record["s#"],
            "ff": record["ff"],
            "ci": record["ci"],
            "sf": 0x01,  # record["sf"],
            "sh": "",
        },
    }

    if missing_csharp:
        del result["properties"]["c#"]

    if upper_case_props:
        result["properties"] = {
            key.upper(): val for (key, val) in result["properties"].items()
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

    service = accessory.add_service(ServicesTypes.LIGHTBULB)
    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = 0

    bridge.add_accessory(accessory)

    return controller.add_device(bridge)


@pytest.mark.parametrize("upper_case_props", [True, False])
@pytest.mark.parametrize("missing_csharp", [True, False])
async def test_discovery_works(hass, controller, upper_case_props, missing_csharp):
    """Test a device being discovered."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device, upper_case_props, missing_csharp)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "source": "zeroconf",
        "title_placeholders": {"name": "TestDevice"},
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


async def test_abort_duplicate_flow(hass, controller):
    """Already paired."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_pair_already_paired_1(hass, controller):
    """Already paired."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Flag device as already paired
    discovery_info["properties"]["sf"] = 0x0

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_paired"


async def test_discovery_ignored_model(hass, controller):
    """Already paired."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)
    discovery_info["properties"]["md"] = config_flow.HOMEKIT_IGNORE[0]

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] == "abort"
    assert result["reason"] == "ignored_model"


async def test_discovery_invalid_config_entry(hass, controller):
    """There is already a config entry for the pairing id but it's invalid."""
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
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )

    # Discovery of a HKID that is in a pairable state but for which there is
    # already a config entry - in that case the stale config entry is
    # automatically removed.
    config_entry_count = len(hass.config_entries.async_entries())
    assert config_entry_count == 0

    # And new config flow should continue allowing user to set up a new pairing
    assert result["type"] == "form"


async def test_discovery_already_configured(hass, controller):
    """Already configured."""
    MockConfigEntry(
        domain="homekit_controller",
        data={"AccessoryPairingID": "00:00:00:00:00:00"},
        unique_id="00:00:00:00:00:00",
    ).add_to_hass(hass)

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Set device as already paired
    discovery_info["properties"]["sf"] = 0x00

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("exception,expected", PAIRING_START_ABORT_ERRORS)
async def test_pair_abort_errors_on_start(hass, controller, exception, expected):
    """Test various pairing errors."""

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )

    # User initiates pairing - device refuses to enter pairing mode
    test_exc = exception("error")
    with patch.object(device, "start_pairing", side_effect=test_exc):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "abort"
    assert result["reason"] == expected


@pytest.mark.parametrize("exception,expected", PAIRING_START_FORM_ERRORS)
async def test_pair_form_errors_on_start(hass, controller, exception, expected):
    """Test various pairing errors."""

    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )

    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "zeroconf",
    }

    # User initiates pairing - device refuses to enter pairing mode
    test_exc = exception("error")
    with patch.object(device, "start_pairing", side_effect=test_exc):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == expected

    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "zeroconf",
    }


@pytest.mark.parametrize("exception,expected", PAIRING_FINISH_ABORT_ERRORS)
async def test_pair_abort_errors_on_finish(hass, controller, exception, expected):
    """Test various pairing errors."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )

    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "zeroconf",
    }

    # User initiates pairing - this triggers the device to show a pairing code
    # and then HA to show a pairing form
    finish_pairing = asynctest.CoroutineMock(side_effect=exception("error"))
    with patch.object(device, "start_pairing", return_value=finish_pairing):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "form"
    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "zeroconf",
    }

    # User enters pairing code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == expected


@pytest.mark.parametrize("exception,expected", PAIRING_FINISH_FORM_ERRORS)
async def test_pair_form_errors_on_finish(hass, controller, exception, expected):
    """Test various pairing errors."""
    device = setup_mock_accessory(controller)
    discovery_info = get_device_discovery_info(device)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )

    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "zeroconf",
    }

    # User initiates pairing - this triggers the device to show a pairing code
    # and then HA to show a pairing form
    finish_pairing = asynctest.CoroutineMock(side_effect=exception("error"))
    with patch.object(device, "start_pairing", return_value=finish_pairing):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == "form"
    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "zeroconf",
    }

    # User enters pairing code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == expected

    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "zeroconf",
    }


async def test_user_works(hass, controller):
    """Test user initiated disovers devices."""
    setup_mock_accessory(controller)

    # Device is discovered
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert get_flow_context(hass, result) == {
        "source": "user",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device": "TestDevice"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    assert get_flow_context(hass, result) == {
        "source": "user",
        "unique_id": "00:00:00:00:00:00",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"pairing_code": "111-22-333"}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"


async def test_user_no_devices(hass, controller):
    """Test user initiated pairing where no devices discovered."""
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "user"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"


async def test_user_no_unpaired_devices(hass, controller):
    """Test user initiated pairing where no unpaired devices discovered."""
    device = setup_mock_accessory(controller)

    # Pair the mock device so that it shows as paired in discovery
    finish_pairing = await device.start_pairing(device.device_id)
    await finish_pairing(device.pairing_code)

    # Device discovery is requested
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "user"}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"


async def test_parse_new_homekit_json(hass):
    """Test migrating recent .homekit/pairings.json files."""
    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    service = accessory.add_service(ServicesTypes.LIGHTBULB)
    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = 0

    accessories = Accessories()
    accessories.add_accessory(accessory)

    fake_controller = await setup_platform(hass)
    pairing = await fake_controller.add_paired_device(accessories, "00:00:00:00:00:00")
    pairing.pairing_data = {"AccessoryPairingID": "00:00:00:00:00:00"}

    mock_path = mock.Mock()
    mock_path.exists.side_effect = [True, False]

    read_data = {"00:00:00:00:00:00": pairing.pairing_data}
    mock_open = mock.mock_open(read_data=json.dumps(read_data))

    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 0},
    }

    flow = _setup_flow_handler(hass)

    pairing_cls_imp = (
        "homeassistant.components.homekit_controller.config_flow.IpPairing"
    )

    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        with mock.patch("builtins.open", mock_open):
            with mock.patch("os.path", mock_path):
                result = await flow.async_step_zeroconf(discovery_info)

    assert result["type"] == "create_entry"
    assert result["title"] == "TestDevice"
    assert result["data"]["AccessoryPairingID"] == "00:00:00:00:00:00"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


async def test_parse_old_homekit_json(hass):
    """Test migrating original .homekit/hk-00:00:00:00:00:00 files."""
    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    service = accessory.add_service(ServicesTypes.LIGHTBULB)
    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = 0

    accessories = Accessories()
    accessories.add_accessory(accessory)

    fake_controller = await setup_platform(hass)
    pairing = await fake_controller.add_paired_device(accessories, "00:00:00:00:00:00")
    pairing.pairing_data = {"AccessoryPairingID": "00:00:00:00:00:00"}

    mock_path = mock.Mock()
    mock_path.exists.side_effect = [False, True]

    mock_listdir = mock.Mock()
    mock_listdir.return_value = ["hk-00:00:00:00:00:00", "pairings.json"]

    read_data = {"AccessoryPairingID": "00:00:00:00:00:00"}
    mock_open = mock.mock_open(read_data=json.dumps(read_data))

    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 0},
    }

    flow = _setup_flow_handler(hass)

    pairing_cls_imp = (
        "homeassistant.components.homekit_controller.config_flow.IpPairing"
    )

    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        with mock.patch("builtins.open", mock_open):
            with mock.patch("os.path", mock_path):
                with mock.patch("os.listdir", mock_listdir):
                    result = await flow.async_step_zeroconf(discovery_info)

    assert result["type"] == "create_entry"
    assert result["title"] == "TestDevice"
    assert result["data"]["AccessoryPairingID"] == "00:00:00:00:00:00"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


async def test_parse_overlapping_homekit_json(hass):
    """Test migrating .homekit/pairings.json files when hk- exists too."""
    accessory = Accessory.create_with_info(
        "TestDevice", "example.com", "Test", "0001", "0.1"
    )
    service = accessory.add_service(ServicesTypes.LIGHTBULB)
    on_char = service.add_char(CharacteristicsTypes.ON)
    on_char.value = 0

    accessories = Accessories()
    accessories.add_accessory(accessory)

    fake_controller = await setup_platform(hass)
    pairing = await fake_controller.add_paired_device(accessories)
    pairing.pairing_data = {"AccessoryPairingID": "00:00:00:00:00:00"}

    mock_listdir = mock.Mock()
    mock_listdir.return_value = ["hk-00:00:00:00:00:00", "pairings.json"]

    mock_path = mock.Mock()
    mock_path.exists.side_effect = [True, True]

    # First file to get loaded is .homekit/pairing.json
    read_data_1 = {"00:00:00:00:00:00": {"AccessoryPairingID": "00:00:00:00:00:00"}}
    mock_open_1 = mock.mock_open(read_data=json.dumps(read_data_1))

    # Second file to get loaded is .homekit/hk-00:00:00:00:00:00
    read_data_2 = {"AccessoryPairingID": "00:00:00:00:00:00"}
    mock_open_2 = mock.mock_open(read_data=json.dumps(read_data_2))

    side_effects = [mock_open_1.return_value, mock_open_2.return_value]

    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 0},
    }

    flow = _setup_flow_handler(hass)

    pairing_cls_imp = (
        "homeassistant.components.homekit_controller.config_flow.IpPairing"
    )
    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        with mock.patch("builtins.open", side_effect=side_effects):
            with mock.patch("os.path", mock_path):
                with mock.patch("os.listdir", mock_listdir):
                    result = await flow.async_step_zeroconf(discovery_info)

        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "TestDevice"
    assert result["data"]["AccessoryPairingID"] == "00:00:00:00:00:00"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


async def test_unignore_works(hass, controller):
    """Test rediscovery triggered disovers work."""
    device = setup_mock_accessory(controller)

    # Device is unignored
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": "unignore"},
        data={"unique_id": device.device_id},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert get_flow_context(hass, result) == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
        "source": "unignore",
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


async def test_unignore_ignores_missing_devices(hass, controller):
    """Test rediscovery triggered disovers handle devices that have gone away."""
    setup_mock_accessory(controller)

    # Device is unignored
    result = await hass.config_entries.flow.async_init(
        "homekit_controller",
        context={"source": "unignore"},
        data={"unique_id": "00:00:00:00:00:01"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"
