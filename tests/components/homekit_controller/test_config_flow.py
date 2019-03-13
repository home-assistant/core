"""Tests for homekit_controller config flow."""
import json
from unittest import mock

import homekit

from homeassistant.components.homekit_controller import config_flow
from homeassistant.components.homekit_controller.const import KNOWN_DEVICES
from tests.common import MockConfigEntry
from tests.components.homekit_controller.common import (
    Accessory, FakeService, setup_platform
)


async def test_discovery_works(hass):
    """Test a device being discovered."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    pairing = mock.Mock(pairing_data={
        'AccessoryPairingID': '00:00:00:00:00:00',
    })

    pairing.list_accessories_and_characteristics.return_value = [{
        "aid": 1,
        "services": [{
            "characteristics": [{
                "type": "23",
                "value": "Koogeek-LS1-20833F"
            }],
            "type": "3e",
        }]
    }]

    controller = mock.Mock()
    controller.pairings = {
        '00:00:00:00:00:00': pairing,
    }

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Koogeek-LS1-20833F'
    assert result['data'] == pairing.pairing_data


async def test_discovery_works_upper_case(hass):
    """Test a device being discovered."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'MD': 'TestDevice',
            'ID': '00:00:00:00:00:00',
            'C#': 1,
            'SF': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    pairing = mock.Mock(pairing_data={
        'AccessoryPairingID': '00:00:00:00:00:00',
    })

    pairing.list_accessories_and_characteristics.return_value = [{
        "aid": 1,
        "services": [{
            "characteristics": [{
                "type": "23",
                "value": "Koogeek-LS1-20833F"
            }],
            "type": "3e",
        }]
    }]

    controller = mock.Mock()
    controller.pairings = {
        '00:00:00:00:00:00': pairing,
    }

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Koogeek-LS1-20833F'
    assert result['data'] == pairing.pairing_data


async def test_discovery_works_missing_csharp(hass):
    """Test a device being discovered that has missing mdns attrs."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    pairing = mock.Mock(pairing_data={
        'AccessoryPairingID': '00:00:00:00:00:00',
    })

    pairing.list_accessories_and_characteristics.return_value = [{
        "aid": 1,
        "services": [{
            "characteristics": [{
                "type": "23",
                "value": "Koogeek-LS1-20833F"
            }],
            "type": "3e",
        }]
    }]

    controller = mock.Mock()
    controller.pairings = {
        '00:00:00:00:00:00': pairing,
    }

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Koogeek-LS1-20833F'
    assert result['data'] == pairing.pairing_data


async def test_pair_already_paired_1(hass):
    """Already paired."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 0,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_paired'


async def test_discovery_ignored_model(hass):
    """Already paired."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'BSB002',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'ignored_model'


async def test_discovery_invalid_config_entry(hass):
    """There is already a config entry for the pairing id but its invalid."""
    MockConfigEntry(domain='homekit_controller', data={
        'AccessoryPairingID': '00:00:00:00:00:00'
    }).add_to_hass(hass)

    # We just added a mock config entry so it must be visible in hass
    assert len(hass.config_entries.async_entries()) == 1

    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    # Discovery of a HKID that is in a pairable state but for which there is
    # already a config entry - in that case the stale config entry is
    # automatically removed.
    config_entry_count = len(hass.config_entries.async_entries())
    assert config_entry_count == 0


async def test_discovery_already_configured(hass):
    """Already configured."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 0,
        }
    }

    await setup_platform(hass)

    conn = mock.Mock()
    conn.config_num = 1
    hass.data[KNOWN_DEVICES]['00:00:00:00:00:00'] = conn

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'

    assert conn.async_config_num_changed.call_count == 0


async def test_discovery_already_configured_config_change(hass):
    """Already configured."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 2,
            'sf': 0,
        }
    }

    await setup_platform(hass)

    conn = mock.Mock()
    conn.config_num = 1
    hass.data[KNOWN_DEVICES]['00:00:00:00:00:00'] = conn

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'

    assert conn.async_config_num_changed.call_args == mock.call(2)


async def test_pair_unable_to_pair(hass):
    """Pairing completed without exception, but didn't create a pairing."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    controller = mock.Mock()
    controller.pairings = {}

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })

    assert result['type'] == 'form'
    assert result['errors']['pairing_code'] == 'unable_to_pair'


async def test_pair_authentication_error(hass):
    """Pairing code is incorrect."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    controller = mock.Mock()
    controller.pairings = {}

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        exc = homekit.AuthenticationError('Invalid pairing code')
        controller.perform_pairing.side_effect = exc
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })

    assert result['type'] == 'form'
    assert result['errors']['pairing_code'] == 'authentication_error'


async def test_pair_unknown_error(hass):
    """Pairing failed for an unknown rason."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    controller = mock.Mock()
    controller.pairings = {}

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        exc = homekit.UnknownError('Unknown error')
        controller.perform_pairing.side_effect = exc
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })

    assert result['type'] == 'form'
    assert result['errors']['pairing_code'] == 'unknown_error'


async def test_pair_already_paired(hass):
    """Device is already paired."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_discovery(discovery_info)
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    controller = mock.Mock()
    controller.pairings = {}

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        exc = homekit.UnavailableError('Unavailable error')
        controller.perform_pairing.side_effect = exc
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })

    assert result['type'] == 'abort'
    assert result['reason'] == 'already_paired'


async def test_import_works(hass):
    """Test a device being discovered."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    import_info = {
        'AccessoryPairingID': '00:00:00:00:00:00',
    }

    pairing = mock.Mock(pairing_data={
        'AccessoryPairingID': '00:00:00:00:00:00',
    })

    pairing.list_accessories_and_characteristics.return_value = [{
        "aid": 1,
        "services": [{
            "characteristics": [{
                "type": "23",
                "value": "Koogeek-LS1-20833F"
            }],
            "type": "3e",
        }]
    }]

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    pairing_cls_imp = "homekit.controller.ip_implementation.IpPairing"

    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        result = await flow.async_import_legacy_pairing(
            discovery_info['properties'], import_info)

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Koogeek-LS1-20833F'
    assert result['data'] == pairing.pairing_data


async def test_import_already_configured(hass):
    """Test importing a device from .homekit that is already a ConfigEntry."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    import_info = {
        'AccessoryPairingID': '00:00:00:00:00:00',
    }

    config_entry = MockConfigEntry(
        domain='homekit_controller',
        data=import_info
    )
    config_entry.add_to_hass(hass)

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    result = await flow.async_import_legacy_pairing(
        discovery_info['properties'], import_info)
    assert result['type'] == 'abort'
    assert result['reason'] == 'already_configured'


async def test_user_works(hass):
    """Test user initiated disovers devices."""
    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 1,
        }
    }

    pairing = mock.Mock(pairing_data={
        'AccessoryPairingID': '00:00:00:00:00:00',
    })
    pairing.list_accessories_and_characteristics.return_value = [{
        "aid": 1,
        "services": [{
            "characteristics": [{
                "type": "23",
                "value": "Koogeek-LS1-20833F"
            }],
            "type": "3e",
        }]
    }]

    controller = mock.Mock()
    controller.pairings = {
        '00:00:00:00:00:00': pairing,
    }
    controller.discover.return_value = [
        discovery_info,
    ]

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        result = await flow.async_step_user()
    assert result['type'] == 'form'
    assert result['step_id'] == 'user'

    result = await flow.async_step_user({
        'device': '00:00:00:00:00:00',
    })
    assert result['type'] == 'form'
    assert result['step_id'] == 'pair'

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value = controller
        result = await flow.async_step_pair({
            'pairing_code': '111-22-33',
        })
    assert result['type'] == 'create_entry'
    assert result['title'] == 'Koogeek-LS1-20833F'
    assert result['data'] == pairing.pairing_data


async def test_user_no_devices(hass):
    """Test user initiated pairing where no devices discovered."""
    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value.discover.return_value = []
        result = await flow.async_step_user()

    assert result['type'] == 'abort'
    assert result['reason'] == 'no_devices'


async def test_user_no_unpaired_devices(hass):
    """Test user initiated pairing where no unpaired devices discovered."""
    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 0,
        }
    }

    with mock.patch('homekit.Controller') as controller_cls:
        controller_cls.return_value.discover.return_value = [
            discovery_info,
        ]
        result = await flow.async_step_user()

    assert result['type'] == 'abort'
    assert result['reason'] == 'no_devices'


async def test_parse_new_homekit_json(hass):
    """Test migrating recent .homekit/pairings.json files."""
    service = FakeService('public.hap.service.lightbulb')
    on_char = service.add_characteristic('on')
    on_char.value = 1

    accessory = Accessory('TestDevice', 'example.com', 'Test', '0001', '0.1')
    accessory.services.append(service)

    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add([accessory])
    pairing.pairing_data = {
        'AccessoryPairingID': '00:00:00:00:00:00',
    }

    mock_path = mock.Mock()
    mock_path.exists.side_effect = [True, False]

    read_data = {
        '00:00:00:00:00:00': pairing.pairing_data,
    }
    mock_open = mock.mock_open(read_data=json.dumps(read_data))

    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 0,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    pairing_cls_imp = "homekit.controller.ip_implementation.IpPairing"

    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        with mock.patch('builtins.open', mock_open):
            with mock.patch('os.path', mock_path):
                result = await flow.async_step_discovery(discovery_info)

    assert result['type'] == 'create_entry'
    assert result['title'] == 'TestDevice'
    assert result['data']['AccessoryPairingID'] == '00:00:00:00:00:00'


async def test_parse_old_homekit_json(hass):
    """Test migrating original .homekit/hk-00:00:00:00:00:00 files."""
    service = FakeService('public.hap.service.lightbulb')
    on_char = service.add_characteristic('on')
    on_char.value = 1

    accessory = Accessory('TestDevice', 'example.com', 'Test', '0001', '0.1')
    accessory.services.append(service)

    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add([accessory])
    pairing.pairing_data = {
        'AccessoryPairingID': '00:00:00:00:00:00',
    }

    mock_path = mock.Mock()
    mock_path.exists.side_effect = [False, True]

    mock_listdir = mock.Mock()
    mock_listdir.return_value = [
        'hk-00:00:00:00:00:00',
        'pairings.json'
    ]

    read_data = {
        'AccessoryPairingID': '00:00:00:00:00:00',
    }
    mock_open = mock.mock_open(read_data=json.dumps(read_data))

    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 0,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    pairing_cls_imp = "homekit.controller.ip_implementation.IpPairing"

    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        with mock.patch('builtins.open', mock_open):
            with mock.patch('os.path', mock_path):
                with mock.patch('os.listdir', mock_listdir):
                    result = await flow.async_step_discovery(discovery_info)

    assert result['type'] == 'create_entry'
    assert result['title'] == 'TestDevice'
    assert result['data']['AccessoryPairingID'] == '00:00:00:00:00:00'


async def test_parse_overlapping_homekit_json(hass):
    """Test migrating .homekit/pairings.json files when hk- exists too."""
    service = FakeService('public.hap.service.lightbulb')
    on_char = service.add_characteristic('on')
    on_char.value = 1

    accessory = Accessory('TestDevice', 'example.com', 'Test', '0001', '0.1')
    accessory.services.append(service)

    fake_controller = await setup_platform(hass)
    pairing = fake_controller.add([accessory])
    pairing.pairing_data = {
        'AccessoryPairingID': '00:00:00:00:00:00',
    }

    mock_listdir = mock.Mock()
    mock_listdir.return_value = [
        'hk-00:00:00:00:00:00',
        'pairings.json'
    ]

    mock_path = mock.Mock()
    mock_path.exists.side_effect = [True, True]

    # First file to get loaded is .homekit/pairing.json
    read_data_1 = {
        '00:00:00:00:00:00': {
            'AccessoryPairingID': '00:00:00:00:00:00',
        }
    }
    mock_open_1 = mock.mock_open(read_data=json.dumps(read_data_1))

    # Second file to get loaded is .homekit/hk-00:00:00:00:00:00
    read_data_2 = {
        'AccessoryPairingID': '00:00:00:00:00:00',
    }
    mock_open_2 = mock.mock_open(read_data=json.dumps(read_data_2))

    side_effects = [mock_open_1.return_value, mock_open_2.return_value]

    discovery_info = {
        'host': '127.0.0.1',
        'port': 8080,
        'properties': {
            'md': 'TestDevice',
            'id': '00:00:00:00:00:00',
            'c#': 1,
            'sf': 0,
        }
    }

    flow = config_flow.HomekitControllerFlowHandler()
    flow.hass = hass

    pairing_cls_imp = "homekit.controller.ip_implementation.IpPairing"

    with mock.patch(pairing_cls_imp) as pairing_cls:
        pairing_cls.return_value = pairing
        with mock.patch('builtins.open', side_effect=side_effects):
            with mock.patch('os.path', mock_path):
                with mock.patch('os.listdir', mock_listdir):
                    result = await flow.async_step_discovery(discovery_info)

        await hass.async_block_till_done()

    assert result['type'] == 'create_entry'
    assert result['title'] == 'TestDevice'
    assert result['data']['AccessoryPairingID'] == '00:00:00:00:00:00'
