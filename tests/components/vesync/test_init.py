"""Tests for the init module."""
import logging
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from pytest_unordered import unordered
from pyvesync import VeSync
from syrupy import SnapshotAssertion

from homeassistant.components.vesync import (
    _async_new_device_discovery,
    _async_process_devices,
    async_setup_entry,
)
from homeassistant.components.vesync.const import (
    DOMAIN,
    SERVICE_UPDATE_DEVS,
    VS_BINARY_SENSORS,
    VS_FANS,
    VS_HUMIDIFIERS,
    VS_LIGHTS,
    VS_MANAGER,
    VS_NUMBERS,
    VS_SENSORS,
    VS_SWITCHES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common import FAN_MODEL, HUMIDIFIER_MODEL, get_entities, get_states


async def test_async_setup_entry__not_login(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager: VeSync,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup does not create config entry when not logged in."""
    manager.login = Mock(return_value=False)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock, patch(
        "homeassistant.components.vesync._async_process_devices"
    ) as process_mock, patch.object(
        hass.services, "async_register"
    ) as register_mock:
        assert not await async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        assert setups_mock.call_count == 0
        assert setup_mock.call_count == 0
        assert process_mock.call_count == 0
        assert register_mock.call_count == 0

    assert manager.login.call_count == 1
    assert DOMAIN not in hass.data
    assert "Unable to login to the VeSync server" in caplog.text


async def test_async_setup_entry__no_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync
) -> None:
    """Test setup connects to vesync and creates empty config when no devices."""
    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ) as setup_mock:
        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert setups_mock.call_args.args[1] == []
        assert setup_mock.call_count == 0

    assert manager.login.call_count == 1
    assert hass.data[DOMAIN][VS_MANAGER] == manager
    assert not hass.data[DOMAIN][VS_FANS]
    assert not hass.data[DOMAIN][VS_HUMIDIFIERS]
    assert not hass.data[DOMAIN][VS_LIGHTS]
    assert not hass.data[DOMAIN][VS_NUMBERS]
    assert not hass.data[DOMAIN][VS_SENSORS]
    assert not hass.data[DOMAIN][VS_SWITCHES]


async def test_async_setup_entry__with_devices(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    manager_devices: VeSync,
    humid_features,
) -> None:
    """Test setup connects to vesync and loads fan platform."""
    with patch.object(
        hass,
        "async_add_executor_job",
        new=AsyncMock(),
    ) as mock_add_executor_job, patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as setups_mock, patch.object(
        hass.services, "async_register"
    ) as register_mock, patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        assert await async_setup_entry(hass, config_entry)
        # Assert platforms loaded
        await hass.async_block_till_done()

        assert mock_add_executor_job.call_count == 2
        assert mock_add_executor_job.call_args_list == [
            call(manager_devices.login),
            call(manager_devices.update),
        ]
        assert setups_mock.call_count == 1
        assert setups_mock.call_args.args[0] == config_entry
        assert list(setups_mock.call_args.args[1]) == [
            Platform.SWITCH,
            Platform.FAN,
            Platform.HUMIDIFIER,
            Platform.LIGHT,
            Platform.SENSOR,
            Platform.NUMBER,
            Platform.BINARY_SENSOR,
        ]
        assert register_mock.call_count == 1
        assert register_mock.call_args.args[0] == DOMAIN
        assert register_mock.call_args.args[1] == SERVICE_UPDATE_DEVS
        assert callable(register_mock.call_args.args[2])

    assert hass.data[DOMAIN][VS_MANAGER] == manager_devices
    assert len(hass.data[DOMAIN][VS_BINARY_SENSORS]) == 3
    assert len(hass.data[DOMAIN][VS_FANS]) == 1
    assert len(hass.data[DOMAIN][VS_HUMIDIFIERS]) == 2
    assert len(hass.data[DOMAIN][VS_LIGHTS]) == 5
    assert len(hass.data[DOMAIN][VS_NUMBERS]) == 3
    assert len(hass.data[DOMAIN][VS_SENSORS]) == 4
    assert len(hass.data[DOMAIN][VS_SWITCHES]) == 5


async def test_asynch_setup_entry__loaded_state(
    hass: HomeAssistant,
    setup_platform,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the resulting setup state is as expected."""

    # humidifier devices
    states = {}
    identifier = "200s-humidifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 8
    states[identifier] = get_states(hass, entities)

    identifier = "600s-humidifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 9
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="humidifiers")

    # fan devices
    states = {}
    identifier = "air-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 3
    states[identifier] = get_states(hass, entities)

    identifier = "asd_sdfKIHG7IJHGwJGJ7GJ_ag5h3G55"
    entities = get_entities(hass, identifier)
    assert len(entities) == 3
    states[identifier] = get_states(hass, entities)

    identifier = "400s-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 5
    states[identifier] = get_states(hass, entities)

    identifier = "600s-purifier"
    entities = get_entities(hass, identifier)
    assert len(entities) == 5
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="fans")

    # bulb devices
    states = {}
    identifier = "dimmable-bulb"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    identifier = "tunable-bulb"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="bulbs")

    # outlet devices
    states = {}
    identifier = "outlet"
    entities = get_entities(hass, identifier)
    assert len(entities) == 7
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="outlets")

    # switch devices
    states = {}
    identifier = "dimmable-switch"
    entities = get_entities(hass, identifier)
    assert len(entities) == 1
    states[identifier] = get_states(hass, entities)

    assert states == snapshot(name="switches")


async def test_async_process_devices__no_devices(
    hass: HomeAssistant, manager, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with no devices is processed."""
    manager = MagicMock()
    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        devices = await _async_process_devices(hass, manager)
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update

    assert devices == {
        "binary_sensors": [],
        "fans": [],
        "humidifiers": [],
        "lights": [],
        "numbers": [],
        "sensors": [],
        "switches": [],
    }
    assert caplog.messages[0] == "0 VeSync fans found"
    assert caplog.messages[1] == "0 VeSync humidifiers found"
    assert caplog.messages[2] == "0 VeSync lights found"
    assert caplog.messages[3] == "0 VeSync outlets found"
    assert caplog.messages[4] == "0 VeSync switches found"


async def test_async_process_devices__devices(
    hass: HomeAssistant, manager, humid_features, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    humidifier1 = MagicMock()
    humidifier1.device_type = HUMIDIFIER_MODEL
    humidifier1.night_light = True
    humidifier2 = MagicMock()
    humidifier2.device_type = HUMIDIFIER_MODEL
    humidifier2.night_light = False
    manager.fans = [fan, humidifier1, humidifier2]

    bulb = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    manager.switches = [switch, light]

    with patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features, patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        devices = await _async_process_devices(hass, manager)
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update

    assert devices == {
        "binary_sensors": [fan, humidifier1, humidifier2],
        "fans": [fan],
        "humidifiers": [humidifier1, humidifier2],
        "lights": [fan, humidifier1, humidifier2, bulb, light],
        "numbers": [fan, humidifier1, humidifier2],
        "sensors": [fan, humidifier1, humidifier2, outlet],
        "switches": [fan, humidifier1, humidifier2, outlet, switch],
    }
    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "2 VeSync humidifiers found"
    assert caplog.messages[2] == "1 VeSync lights found"
    assert caplog.messages[3] == "1 VeSync outlets found"
    assert caplog.messages[4] == "2 VeSync switches found"


async def test_async_new_device_discovery__no_devices(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when manager with no devices is discovered."""
    manager = MagicMock()

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager
    hass.data[DOMAIN][VS_BINARY_SENSORS]: list = []
    hass.data[DOMAIN][VS_FANS]: list = []
    hass.data[DOMAIN][VS_HUMIDIFIERS]: list = []
    hass.data[DOMAIN][VS_LIGHTS]: list = []
    hass.data[DOMAIN][VS_NUMBERS]: list = []
    hass.data[DOMAIN][VS_SENSORS]: list = []
    hass.data[DOMAIN][VS_SWITCHES]: list = []

    mock_forward_setup = Mock()
    mock_service = Mock()
    with patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job:
        await _async_new_device_discovery(
            hass, config_entry, mock_forward_setup, mock_service
        )
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update
        mock_forward_setup.assert_not_called()
        mock_service.assert_not_called()

    assert caplog.messages[0] == "0 VeSync fans found"
    assert caplog.messages[1] == "0 VeSync humidifiers found"
    assert caplog.messages[2] == "0 VeSync lights found"
    assert caplog.messages[3] == "0 VeSync outlets found"
    assert caplog.messages[4] == "0 VeSync switches found"


async def test_async_new_device_discovery__start_empty_discover_devices(
    hass: HomeAssistant,
    config_entry,
    manager,
    humid_features,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    humidifier1 = MagicMock()
    humidifier1.device_type = HUMIDIFIER_MODEL
    humidifier1.night_light = True
    humidifier2 = MagicMock()
    humidifier2.device_type = HUMIDIFIER_MODEL
    humidifier2.night_light = False
    humidifier3 = MagicMock()
    humidifier3.device_type = HUMIDIFIER_MODEL
    humidifier3.night_light = False
    manager.fans = [fan, humidifier1, humidifier2]

    bulb = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    manager.switches = [switch, light]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager
    hass.data[DOMAIN][VS_BINARY_SENSORS]: list = []
    hass.data[DOMAIN][VS_FANS]: list = []
    hass.data[DOMAIN][VS_HUMIDIFIERS]: list = []
    hass.data[DOMAIN][VS_LIGHTS]: list = []
    hass.data[DOMAIN][VS_NUMBERS]: list = []
    hass.data[DOMAIN][VS_SENSORS]: list = []
    hass.data[DOMAIN][VS_SWITCHES]: list = []

    mock_forward_setup = Mock()
    mock_service = Mock()
    with patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features, patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job, patch(
        "homeassistant.components.vesync.async_dispatcher_send"
    ) as mock_dispatcher_send, patch.object(
        hass, "async_create_task", new=Mock()
    ) as mock_create_task:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        await _async_new_device_discovery(
            hass, config_entry, mock_forward_setup, mock_service
        )
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update
        assert mock_dispatcher_send.call_count == 0
        assert mock_create_task.call_count == 7
        assert mock_forward_setup.call_count == 7
        mock_forward_setup.assert_has_calls(
            [
                call(config_entry, Platform.SWITCH),
                call(config_entry, Platform.FAN),
                call(config_entry, Platform.LIGHT),
                call(config_entry, Platform.HUMIDIFIER),
                call(config_entry, Platform.NUMBER),
                call(config_entry, Platform.SENSOR),
                call(config_entry, Platform.BINARY_SENSOR),
            ]
        )
        mock_service.assert_not_called()

    assert hass.data[DOMAIN][VS_BINARY_SENSORS] == unordered(
        [fan, humidifier1, humidifier2]
    )
    assert hass.data[DOMAIN][VS_FANS] == unordered([fan])
    assert hass.data[DOMAIN][VS_HUMIDIFIERS] == unordered([humidifier1, humidifier2])
    assert hass.data[DOMAIN][VS_LIGHTS] == unordered(
        [fan, humidifier1, humidifier2, bulb, light]
    )
    assert hass.data[DOMAIN][VS_NUMBERS] == unordered([fan, humidifier1, humidifier2])
    assert hass.data[DOMAIN][VS_SENSORS] == unordered(
        [fan, humidifier1, humidifier2, outlet]
    )
    assert hass.data[DOMAIN][VS_SWITCHES] == unordered(
        [fan, humidifier1, humidifier2, outlet, switch]
    )

    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "2 VeSync humidifiers found"
    assert caplog.messages[2] == "1 VeSync lights found"
    assert caplog.messages[3] == "1 VeSync outlets found"
    assert caplog.messages[4] == "2 VeSync switches found"


async def test_async_new_device_discovery__start_devices_discover_devices(
    hass: HomeAssistant,
    config_entry,
    manager,
    humid_features,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when manager with devices is processed."""
    caplog.set_level(logging.INFO)

    fan = MagicMock()
    fan.device_type = FAN_MODEL
    fan2 = MagicMock()
    fan2.device_type = FAN_MODEL
    humidifier1 = MagicMock()
    humidifier1.device_type = HUMIDIFIER_MODEL
    humidifier1.night_light = True
    humidifier2 = MagicMock()
    humidifier2.device_type = HUMIDIFIER_MODEL
    humidifier2.night_light = False
    humidifier3 = MagicMock()
    humidifier3.device_type = HUMIDIFIER_MODEL
    humidifier3.night_light = True
    manager.fans = [fan, humidifier1, humidifier2]

    bulb = MagicMock()
    bulb2 = MagicMock()
    manager.bulbs = [bulb]

    outlet = MagicMock()
    outlet2 = MagicMock()
    manager.outlets = [outlet]

    switch = MagicMock()
    switch.is_dimmable.return_value = False
    switch2 = MagicMock()
    switch2.is_dimmable.return_value = False
    light = MagicMock()
    light.is_dimmable.return_value = True
    light2 = MagicMock()
    light2.is_dimmable.return_value = True
    manager.switches = [switch, light]

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager
    hass.data[DOMAIN][VS_BINARY_SENSORS]: list = [humidifier3]
    hass.data[DOMAIN][VS_FANS]: list = [fan2]
    hass.data[DOMAIN][VS_HUMIDIFIERS]: list = [humidifier3]
    hass.data[DOMAIN][VS_LIGHTS]: list = [bulb2, light2]
    hass.data[DOMAIN][VS_NUMBERS]: list = [humidifier3]
    hass.data[DOMAIN][VS_SENSORS]: list = [outlet2]
    hass.data[DOMAIN][VS_SWITCHES]: list = [switch2]

    mock_forward_setup = Mock()
    mock_service = Mock()
    with patch(
        "homeassistant.components.vesync.common.humid_features"
    ) as mock_features, patch.object(
        hass, "async_add_executor_job", new=AsyncMock()
    ) as mock_add_executor_job, patch(
        "homeassistant.components.vesync.async_dispatcher_send"
    ) as mock_dispatcher_send, patch.object(
        hass, "async_create_task", new=Mock()
    ) as mock_create_task:
        mock_features.values.side_effect = humid_features.values
        mock_features.keys.side_effect = humid_features.keys

        await _async_new_device_discovery(
            hass, config_entry, mock_forward_setup, mock_service
        )
        assert mock_add_executor_job.call_count == 1
        assert mock_add_executor_job.call_args[0][0] == manager.update
        assert mock_dispatcher_send.call_count == 7
        assert mock_dispatcher_send.mock_calls[0] == call(
            hass,
            "vesync_discovery_switches",
            unordered([fan, humidifier1, humidifier2, outlet, switch]),
        )
        assert mock_dispatcher_send.mock_calls[1] == call(
            hass, "vesync_discovery_fans", unordered([fan])
        )
        assert mock_dispatcher_send.mock_calls[2] == call(
            hass,
            "vesync_discovery_lights",
            unordered([fan, humidifier1, humidifier2, bulb, light]),
        )
        assert mock_dispatcher_send.mock_calls[3] == call(
            hass, "vesync_discovery_humidifiers", unordered([humidifier1, humidifier2])
        )
        assert mock_dispatcher_send.mock_calls[4] == call(
            hass, "vesync_discovery_numbers", unordered([fan, humidifier1, humidifier2])
        )
        assert mock_dispatcher_send.mock_calls[5] == call(
            hass,
            "vesync_discovery_sensors",
            unordered([fan, humidifier1, humidifier2, outlet]),
        )
        assert mock_dispatcher_send.mock_calls[6] == call(
            hass,
            "vesync_discovery_binary_sensors",
            unordered([fan, humidifier1, humidifier2]),
        )
        assert mock_create_task.call_count == 0
        assert mock_forward_setup.call_count == 0
        mock_service.assert_not_called()

    assert hass.data[DOMAIN][VS_BINARY_SENSORS] == unordered(
        [fan, humidifier1, humidifier2, humidifier3]
    )
    assert hass.data[DOMAIN][VS_FANS] == unordered([fan, fan2])
    assert hass.data[DOMAIN][VS_HUMIDIFIERS] == unordered(
        [humidifier1, humidifier2, humidifier3]
    )
    assert hass.data[DOMAIN][VS_LIGHTS] == unordered(
        [fan, humidifier1, humidifier2, bulb, bulb2, light, light2]
    )

    assert hass.data[DOMAIN][VS_NUMBERS] == unordered(
        [fan, humidifier1, humidifier2, humidifier3]
    )
    assert hass.data[DOMAIN][VS_SENSORS] == unordered(
        [fan, humidifier1, humidifier2, outlet, outlet2]
    )
    assert hass.data[DOMAIN][VS_SWITCHES] == unordered(
        [
            fan,
            humidifier1,
            humidifier2,
            outlet,
            switch,
            switch2,
        ]
    )

    assert caplog.messages[0] == "1 VeSync fans found"
    assert caplog.messages[1] == "2 VeSync humidifiers found"
    assert caplog.messages[2] == "1 VeSync lights found"
    assert caplog.messages[3] == "1 VeSync outlets found"
    assert caplog.messages[4] == "2 VeSync switches found"
