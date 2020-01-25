"""Tests for homekit_controller config flow."""
import json
from unittest import mock

import homekit
import pytest

from homeassistant.components.homekit_controller import config_flow
from homeassistant.components.homekit_controller.const import KNOWN_DEVICES

from tests.common import MockConfigEntry
from tests.components.homekit_controller.common import (
    Accessory,
    FakeService,
    setup_platform,
)

PAIRING_START_FORM_ERRORS = [
    (homekit.BusyError, "busy_error"),
    (homekit.MaxTriesError, "max_tries_error"),
    (KeyError, "pairing_failed"),
]

PAIRING_START_ABORT_ERRORS = [
    (homekit.AccessoryNotFoundError, "accessory_not_found_error"),
    (homekit.UnavailableError, "already_paired"),
]

PAIRING_FINISH_FORM_ERRORS = [
    (homekit.exceptions.MalformedPinError, "authentication_error"),
    (homekit.MaxPeersError, "max_peers_error"),
    (homekit.AuthenticationError, "authentication_error"),
    (homekit.UnknownError, "unknown_error"),
    (KeyError, "pairing_failed"),
]

PAIRING_FINISH_ABORT_ERRORS = [
    (homekit.AccessoryNotFoundError, "accessory_not_found_error")
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


def _setup_flow_handler(hass):
    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass
    flow.context = {}

    flow.controller = mock.Mock()
    flow.controller.pairings = {}

    return flow


async def _setup_flow_zeroconf(hass, discovery_info):
    result = await hass.config_entries.flow.async_init(
        "homekit_controller", context={"source": "zeroconf"}, data=discovery_info
    )
    return result


@pytest.mark.parametrize("pairing_code", INVALID_PAIRING_CODES)
def test_invalid_pairing_codes(pairing_code):
    """Test ensure_pin_format raises for an invalid pin code."""
    with pytest.raises(homekit.exceptions.MalformedPinError):
        config_flow.ensure_pin_format(pairing_code)


@pytest.mark.parametrize("pairing_code", VALID_PAIRING_CODES)
def test_valid_pairing_codes(pairing_code):
    """Test ensure_pin_format corrects format for a valid pin in an alternative format."""
    valid_pin = config_flow.ensure_pin_format(pairing_code).split("-")
    assert len(valid_pin) == 3
    assert len(valid_pin[0]) == 3
    assert len(valid_pin[1]) == 2
    assert len(valid_pin[2]) == 3


async def test_discovery_works(hass):
    """Test a device being discovered."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device enters pairing mode and displays code
    result = await flow.async_step_pair({})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.controller.start_pairing.call_count == 1

    pairing = mock.Mock(pairing_data={"AccessoryPairingID": "00:00:00:00:00:00"})

    pairing.list_accessories_and_characteristics.return_value = [
        {
            "aid": 1,
            "services": [
                {
                    "characteristics": [{"type": "23", "value": "Koogeek-LS1-20833F"}],
                    "type": "3e",
                }
            ],
        }
    ]

    # Pairing doesn't error error and pairing results
    flow.controller.pairings = {"00:00:00:00:00:00": pairing}
    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == pairing.pairing_data


async def test_discovery_works_upper_case(hass):
    """Test a device being discovered."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"MD": "TestDevice", "ID": "00:00:00:00:00:00", "C#": 1, "SF": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device enters pairing mode and displays code
    result = await flow.async_step_pair({})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.controller.start_pairing.call_count == 1

    pairing = mock.Mock(pairing_data={"AccessoryPairingID": "00:00:00:00:00:00"})

    pairing.list_accessories_and_characteristics.return_value = [
        {
            "aid": 1,
            "services": [
                {
                    "characteristics": [{"type": "23", "value": "Koogeek-LS1-20833F"}],
                    "type": "3e",
                }
            ],
        }
    ]

    flow.controller.pairings = {"00:00:00:00:00:00": pairing}
    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == pairing.pairing_data


async def test_discovery_works_missing_csharp(hass):
    """Test a device being discovered that has missing mdns attrs."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device enters pairing mode and displays code
    result = await flow.async_step_pair({})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.controller.start_pairing.call_count == 1

    pairing = mock.Mock(pairing_data={"AccessoryPairingID": "00:00:00:00:00:00"})

    pairing.list_accessories_and_characteristics.return_value = [
        {
            "aid": 1,
            "services": [
                {
                    "characteristics": [{"type": "23", "value": "Koogeek-LS1-20833F"}],
                    "type": "3e",
                }
            ],
        }
    ]

    flow.controller.pairings = {"00:00:00:00:00:00": pairing}

    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == pairing.pairing_data


async def test_abort_duplicate_flow(hass):
    """Already paired."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    result = await _setup_flow_zeroconf(hass, discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    result = await _setup_flow_zeroconf(hass, discovery_info)
    assert result["type"] == "abort"
    assert result["reason"] == "already_in_progress"


async def test_pair_already_paired_1(hass):
    """Already paired."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 0},
    }

    flow = _setup_flow_handler(hass)

    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "abort"
    assert result["reason"] == "already_paired"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


async def test_discovery_ignored_model(hass):
    """Already paired."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {
            "md": config_flow.HOMEKIT_IGNORE[0],
            "id": "00:00:00:00:00:00",
            "c#": 1,
            "sf": 1,
        },
    }

    flow = _setup_flow_handler(hass)

    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "abort"
    assert result["reason"] == "ignored_model"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


async def test_discovery_invalid_config_entry(hass):
    """There is already a config entry for the pairing id but its invalid."""
    MockConfigEntry(
        domain="homekit_controller", data={"AccessoryPairingID": "00:00:00:00:00:00"}
    ).add_to_hass(hass)

    # We just added a mock config entry so it must be visible in hass
    assert len(hass.config_entries.async_entries()) == 1

    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # Discovery of a HKID that is in a pairable state but for which there is
    # already a config entry - in that case the stale config entry is
    # automatically removed.
    config_entry_count = len(hass.config_entries.async_entries())
    assert config_entry_count == 0


async def test_discovery_already_configured(hass):
    """Already configured."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 0},
    }

    await setup_platform(hass)

    conn = mock.Mock()
    conn.config_num = 1
    hass.data[KNOWN_DEVICES]["00:00:00:00:00:00"] = conn

    flow = _setup_flow_handler(hass)

    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert flow.context == {}

    assert conn.async_config_num_changed.call_count == 0


async def test_discovery_already_configured_config_change(hass):
    """Already configured."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 2, "sf": 0},
    }

    await setup_platform(hass)

    conn = mock.Mock()
    conn.config_num = 1
    hass.data[KNOWN_DEVICES]["00:00:00:00:00:00"] = conn

    flow = _setup_flow_handler(hass)

    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert flow.context == {}

    assert conn.async_refresh_entity_map.call_args == mock.call(2)


async def test_pair_unable_to_pair(hass):
    """Pairing completed without exception, but didn't create a pairing."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device enters pairing mode and displays code
    result = await flow.async_step_pair({})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.controller.start_pairing.call_count == 1

    # Pairing doesn't error but no pairing object is generated
    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == "unable_to_pair"


@pytest.mark.parametrize("exception,expected", PAIRING_START_ABORT_ERRORS)
async def test_pair_abort_errors_on_start(hass, exception, expected):
    """Test various pairing errors."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device refuses to enter pairing mode
    with mock.patch.object(flow.controller, "start_pairing") as start_pairing:
        start_pairing.side_effect = exception("error")
        result = await flow.async_step_pair({})

    assert result["type"] == "abort"
    assert result["reason"] == expected
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


@pytest.mark.parametrize("exception,expected", PAIRING_START_FORM_ERRORS)
async def test_pair_form_errors_on_start(hass, exception, expected):
    """Test various pairing errors."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device refuses to enter pairing mode
    with mock.patch.object(flow.controller, "start_pairing") as start_pairing:
        start_pairing.side_effect = exception("error")
        result = await flow.async_step_pair({})

    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == expected
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


@pytest.mark.parametrize("exception,expected", PAIRING_FINISH_ABORT_ERRORS)
async def test_pair_abort_errors_on_finish(hass, exception, expected):
    """Test various pairing errors."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device enters pairing mode and displays code
    result = await flow.async_step_pair({})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.controller.start_pairing.call_count == 1

    # User submits code - pairing fails but can be retried
    flow.finish_pairing.side_effect = exception("error")
    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "abort"
    assert result["reason"] == expected
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


@pytest.mark.parametrize("exception,expected", PAIRING_FINISH_FORM_ERRORS)
async def test_pair_form_errors_on_finish(hass, exception, expected):
    """Test various pairing errors."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    flow = _setup_flow_handler(hass)

    # Device is discovered
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing - device enters pairing mode and displays code
    result = await flow.async_step_pair({})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.controller.start_pairing.call_count == 1

    # User submits code - pairing fails but can be retried
    flow.finish_pairing.side_effect = exception("error")
    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "form"
    assert result["errors"]["pairing_code"] == expected
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }


async def test_import_works(hass):
    """Test a device being discovered."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    import_info = {"AccessoryPairingID": "00:00:00:00:00:00"}

    pairing = mock.Mock(pairing_data={"AccessoryPairingID": "00:00:00:00:00:00"})

    pairing.list_accessories_and_characteristics.return_value = [
        {
            "aid": 1,
            "services": [
                {
                    "characteristics": [{"type": "23", "value": "Koogeek-LS1-20833F"}],
                    "type": "3e",
                }
            ],
        }
    ]

    flow = _setup_flow_handler(hass)

    pairing_cls_imp = (
        "homeassistant.components.homekit_controller.config_flow.IpPairing"
    )

    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        result = await flow.async_import_legacy_pairing(
            discovery_info["properties"], import_info
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == pairing.pairing_data


async def test_import_already_configured(hass):
    """Test importing a device from .homekit that is already a ConfigEntry."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "properties": {"md": "TestDevice", "id": "00:00:00:00:00:00", "c#": 1, "sf": 1},
    }

    import_info = {"AccessoryPairingID": "00:00:00:00:00:00"}

    config_entry = MockConfigEntry(domain="homekit_controller", data=import_info)
    config_entry.add_to_hass(hass)

    flow = _setup_flow_handler(hass)

    result = await flow.async_import_legacy_pairing(
        discovery_info["properties"], import_info
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_user_works(hass):
    """Test user initiated disovers devices."""
    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "md": "TestDevice",
        "id": "00:00:00:00:00:00",
        "c#": 1,
        "sf": 1,
    }

    pairing = mock.Mock(pairing_data={"AccessoryPairingID": "00:00:00:00:00:00"})
    pairing.list_accessories_and_characteristics.return_value = [
        {
            "aid": 1,
            "services": [
                {
                    "characteristics": [{"type": "23", "value": "Koogeek-LS1-20833F"}],
                    "type": "3e",
                }
            ],
        }
    ]

    flow = _setup_flow_handler(hass)

    flow.controller.pairings = {"00:00:00:00:00:00": pairing}
    flow.controller.discover.return_value = [discovery_info]

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await flow.async_step_user({"device": "TestDevice"})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"

    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == pairing.pairing_data


async def test_user_no_devices(hass):
    """Test user initiated pairing where no devices discovered."""
    flow = _setup_flow_handler(hass)

    flow.controller.discover.return_value = []
    result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"


async def test_user_no_unpaired_devices(hass):
    """Test user initiated pairing where no unpaired devices discovered."""
    flow = _setup_flow_handler(hass)

    discovery_info = {
        "name": "TestDevice",
        "host": "127.0.0.1",
        "port": 8080,
        "md": "TestDevice",
        "id": "00:00:00:00:00:00",
        "c#": 1,
        "sf": 0,
    }

    flow.controller.discover.return_value = [discovery_info]
    result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices"


async def test_parse_new_homekit_json(hass):
    """Test migrating recent .homekit/pairings.json files."""
    service = FakeService("public.hap.service.lightbulb")
    on_char = service.add_characteristic("on")
    on_char.value = 1

    accessory = Accessory("TestDevice", "example.com", "Test", "0001", "0.1")
    accessory.services.append(service)

    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add([accessory])
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
    service = FakeService("public.hap.service.lightbulb")
    on_char = service.add_characteristic("on")
    on_char.value = 1

    accessory = Accessory("TestDevice", "example.com", "Test", "0001", "0.1")
    accessory.services.append(service)

    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add([accessory])
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
    service = FakeService("public.hap.service.lightbulb")
    on_char = service.add_characteristic("on")
    on_char.value = 1

    accessory = Accessory("TestDevice", "example.com", "Test", "0001", "0.1")
    accessory.services.append(service)

    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add([accessory])
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


async def test_unignore_works(hass):
    """Test rediscovery triggered disovers work."""
    discovery_info = {
        "name": "TestDevice",
        "address": "127.0.0.1",
        "port": 8080,
        "md": "TestDevice",
        "pv": "1.0",
        "id": "00:00:00:00:00:00",
        "c#": 1,
        "s#": 1,
        "ff": 0,
        "ci": 0,
        "sf": 1,
    }

    pairing = mock.Mock(pairing_data={"AccessoryPairingID": "00:00:00:00:00:00"})
    pairing.list_accessories_and_characteristics.return_value = [
        {
            "aid": 1,
            "services": [
                {
                    "characteristics": [{"type": "23", "value": "Koogeek-LS1-20833F"}],
                    "type": "3e",
                }
            ],
        }
    ]

    flow = _setup_flow_handler(hass)

    flow.controller.pairings = {"00:00:00:00:00:00": pairing}
    flow.controller.discover.return_value = [discovery_info]

    result = await flow.async_step_unignore({"unique_id": "00:00:00:00:00:00"})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.context == {
        "hkid": "00:00:00:00:00:00",
        "title_placeholders": {"name": "TestDevice"},
        "unique_id": "00:00:00:00:00:00",
    }

    # User initiates pairing by clicking on 'configure' - device enters pairing mode and displays code
    result = await flow.async_step_pair({})
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert flow.controller.start_pairing.call_count == 1

    # Pairing finalized
    result = await flow.async_step_pair({"pairing_code": "111-22-333"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Koogeek-LS1-20833F"
    assert result["data"] == pairing.pairing_data


async def test_unignore_ignores_missing_devices(hass):
    """Test rediscovery triggered disovers handle devices that have gone away."""
    discovery_info = {
        "name": "TestDevice",
        "address": "127.0.0.1",
        "port": 8080,
        "md": "TestDevice",
        "pv": "1.0",
        "id": "00:00:00:00:00:00",
        "c#": 1,
        "s#": 1,
        "ff": 0,
        "ci": 0,
        "sf": 1,
    }

    flow = _setup_flow_handler(hass)
    flow.controller.discover.return_value = [discovery_info]

    result = await flow.async_step_unignore({"unique_id": "00:00:00:00:00:01"})
    assert result["type"] == "abort"
    assert flow.context == {
        "unique_id": "00:00:00:00:00:01",
    }
