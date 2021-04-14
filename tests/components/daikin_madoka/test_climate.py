"""The sensor tests for the tado platform."""


import json
from unittest.mock import MagicMock, patch

from homeassistant import setup
from homeassistant.components.climate.const import (
    ATTR_HVAC_ACTION,
    FAN_HIGH,
    HVAC_MODE_DRY,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from . import (
    TEST_DISCOVERED_DEVICES,
    async_init_integration,
    create_controller_aborted,
    create_controller_disconnected,
    create_controller_empty_status,
    create_controller_mock,
    create_controller_update_error,
    prepare_fixture,
)

from tests.common import load_fixture

ATTRIBUTE_KEYS = [
    "current_temperature",
    "fan_mode",
    "fan_modes",
    "hvac_action",
    "hvac_modes",
    "max_temp",
    "min_temp",
    "supported_features",
    "target_temp_step",
    "temperature",
]


async def test_climate_connection_error(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):
        fixture = json.loads(load_fixture("daikin_madoka/mode_auto_cooling.json"))

        controller_mock = create_controller_update_error(fixture)

        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")

        assert state.state == STATE_UNAVAILABLE


async def test_async_setup_entry_aborted(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):
        fixture = json.loads(load_fixture("daikin_madoka/controller_aborted.json"))

        controller_mock = create_controller_aborted(fixture, False, True)

        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")

        assert state.state == STATE_UNAVAILABLE


async def test_climate_connection_aborted(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):
        fixture = json.loads(load_fixture("daikin_madoka/controller_aborted.json"))

        controller_mock = create_controller_aborted(fixture, True, False)

        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")

        assert state.state == STATE_UNAVAILABLE


async def test_climate_disconnected(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/controller_disconnected.json"))
        controller_mock = create_controller_disconnected(fixture)
        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")
        assert state.state == STATE_UNAVAILABLE


async def test_climate_empty_status(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/controller_disconnected.json"))
        controller_mock = create_controller_empty_status(fixture)
        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")
        assert state.state == STATE_UNKNOWN

        ha_attributes = prepare_fixture(fixture["defaults"])

        check_attributes = {k: ha_attributes[k] for k in ATTRIBUTE_KEYS}
        check_attributes.pop(ATTR_HVAC_ACTION)
        # Only test for a subset of attributes in case
        # HA changes the implementation and a new one appears

        assert all(
            item in state.attributes.items() for item in check_attributes.items()
        )


async def test_climate_mode_auto_cooling(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/mode_auto_cooling.json"))
        controller_mock = create_controller_mock(fixture)
        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")
        assert state.state == fixture["defaults"]["hvac_mode"]

        ha_attributes = prepare_fixture(fixture["defaults"])
        check_attributes = {k: ha_attributes[k] for k in ATTRIBUTE_KEYS}

        # Only test for a subset of attributes in case
        # HA changes the implementation and a new one appears

        assert all(
            item in state.attributes.items() for item in check_attributes.items()
        )


async def test_climate_mode_auto_heating(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/mode_auto_heating.json"))
        controller_mock = create_controller_mock(fixture)
        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")
        assert state.state == fixture["defaults"]["hvac_mode"]

        ha_attributes = prepare_fixture(fixture["defaults"])
        check_attributes = {k: ha_attributes[k] for k in ATTRIBUTE_KEYS}

        # Only test for a subset of attributes in case
        # HA changes the implementation and a new one appears

        assert all(
            item in state.attributes.items() for item in check_attributes.items()
        )


async def test_climate_mode_heat(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/mode_heat.json"))
        controller_mock = create_controller_mock(fixture)
        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")
        assert state.state == fixture["defaults"]["hvac_mode"]

        ha_attributes = prepare_fixture(fixture["defaults"])
        check_attributes = {k: ha_attributes[k] for k in ATTRIBUTE_KEYS}

        # Only test for a subset of attributes in case
        # HA changes the implementation and a new one appears

        assert all(
            item in state.attributes.items() for item in check_attributes.items()
        )


async def test_climate_mode_off(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/mode_off.json"))
        controller_mock = create_controller_mock(fixture)
        await async_init_integration(hass, controller_mock)

        state = hass.states.get("climate.test")
        assert state.state == fixture["defaults"]["hvac_mode"]

        ha_attributes = prepare_fixture(fixture["defaults"])
        check_attributes = {k: ha_attributes[k] for k in ATTRIBUTE_KEYS}

        # Only test for a subset of attributes in case
        # HA changes the implementation and a new one appears

        assert all(
            item in state.attributes.items() for item in check_attributes.items()
        )


async def test_climate_set_values(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/mode_off.json"))
        controller_mock = create_controller_mock(fixture)
        await async_init_integration(hass, controller_mock)

        from homeassistant.components.daikin_madoka.const import DOMAIN
        from homeassistant.helpers.entity_platform import async_get_platforms

        madoka_platforms = async_get_platforms(hass, DOMAIN)
        madoka_climate = None
        for p in madoka_platforms:
            if p.domain == "climate" and "climate.test" in p.entities:
                madoka_climate = p.entities["climate.test"]
                break

        assert madoka_climate is not None
        await madoka_climate.async_set_fan_mode(FAN_HIGH)
        await madoka_climate.async_set_temperature(temperature=27)
        await madoka_climate.async_set_hvac_mode(HVAC_MODE_DRY)
        await madoka_climate.async_turn_on()
        await madoka_climate.async_turn_off()


async def test_climate_set_values_connection_error(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/mode_off.json"))
        controller_mock = create_controller_update_error(fixture)
        await async_init_integration(hass, controller_mock)

        from homeassistant.components.daikin_madoka.const import DOMAIN
        from homeassistant.helpers.entity_platform import async_get_platforms

        madoka_platforms = async_get_platforms(hass, DOMAIN)
        madoka_climate = None
        for p in madoka_platforms:
            if p.domain == "climate" and "climate.test" in p.entities:
                madoka_climate = p.entities["climate.test"]
                break

        assert madoka_climate is not None
        await madoka_climate.async_set_fan_mode(FAN_HIGH)
        await madoka_climate.async_set_temperature(temperature=27)
        await madoka_climate.async_set_hvac_mode(HVAC_MODE_DRY)
        await madoka_climate.async_turn_on()
        await madoka_climate.async_turn_off()


async def test_climate_set_values_aborted_error(hass):
    """Test creation of aircon climate."""
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ):

        fixture = json.loads(load_fixture("daikin_madoka/mode_off.json"))
        controller_mock = create_controller_aborted(fixture, False, True)
        await async_init_integration(hass, controller_mock)

        from homeassistant.components.daikin_madoka.const import DOMAIN
        from homeassistant.helpers.entity_platform import async_get_platforms

        madoka_platforms = async_get_platforms(hass, DOMAIN)
        madoka_climate = None
        for p in madoka_platforms:
            if p.domain == "climate" and "climate.test" in p.entities:
                madoka_climate = p.entities["climate.test"]
                break

        assert madoka_climate is not None
        await madoka_climate.async_set_fan_mode(FAN_HIGH)
        await madoka_climate.async_set_temperature(temperature=27)
        await madoka_climate.async_set_hvac_mode(HVAC_MODE_DRY)
        await madoka_climate.async_turn_on()
        await madoka_climate.async_turn_off()
