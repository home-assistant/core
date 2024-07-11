"""Test Konnected setup process."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.konnected import config_flow, panel
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component
from homeassistant.util import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(name="mock_panel")
async def mock_panel_fixture():
    """Mock a Konnected Panel bridge."""
    with patch("konnected.Client", autospec=True) as konn_client:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            konn_client.host = host
            konn_client.port = port
            return konn_client

        konn_client.side_effect = mock_constructor
        konn_client.ClientError = config_flow.CannotConnect
        konn_client.get_status.return_value = {
            "hwVersion": "2.3.0",
            "swVersion": "2.3.1",
            "heap": 10000,
            "uptime": 12222,
            "ip": "192.168.1.90",
            "port": 9123,
            "sensors": [],
            "actuators": [],
            "dht_sensors": [],
            "ds18b20_sensors": [],
            "mac": "11:22:33:44:55:66",
            "model": "Konnected Pro",  # `model` field only included in pro
            "settings": {},
        }
        yield konn_client


async def test_create_and_setup(hass: HomeAssistant, mock_panel) -> None:
    """Test that we create a Konnected Panel and save the data."""
    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "11223344556677889900",
            "default_options": config_flow.OPTIONS_SCHEMA({config_flow.CONF_IO: {}}),
        }
    )

    device_options = config_flow.OPTIONS_SCHEMA(
        {
            "io": {
                "1": "Binary Sensor",
                "2": "Binary Sensor",
                "3": "Binary Sensor",
                "4": "Digital Sensor",
                "5": "Digital Sensor",
                "6": "Switchable Output",
                "out": "Switchable Output",
            },
            "binary_sensors": [
                {"zone": "1", "type": "door"},
                {"zone": "2", "type": "window", "name": "winder", "inverse": True},
                {"zone": "3", "type": "door"},
            ],
            "sensors": [
                {"zone": "4", "type": "dht"},
                {"zone": "5", "type": "ds18b20", "name": "temper"},
            ],
            "switches": [
                {
                    "zone": "out",
                    "name": "switcher",
                    "activation": "low",
                    "momentary": 50,
                    "pause": 100,
                    "repeat": 4,
                },
                {"zone": "6"},
            ],
        }
    )

    entry = MockConfigEntry(
        domain="konnected",
        title="Konnected Alarm Panel",
        data=device_config,
        options=device_options,
    )
    entry.add_to_hass(hass)

    # override get_status to reflect non-pro board
    mock_panel.get_status.return_value = {
        "hwVersion": "2.3.0",
        "swVersion": "2.3.1",
        "heap": 10000,
        "uptime": 12222,
        "ip": "192.168.1.90",
        "port": 9123,
        "sensors": [],
        "actuators": [],
        "dht_sensors": [],
        "ds18b20_sensors": [],
        "mac": "11:22:33:44:55:66",
        "settings": {},
    }

    # setup the integration and inspect panel behavior
    assert (
        await async_setup_component(
            hass,
            panel.DOMAIN,
            {
                panel.DOMAIN: {
                    panel.CONF_ACCESS_TOKEN: "arandomstringvalue",
                    panel.CONF_API_HOST: "http://192.168.1.1:8123",
                }
            },
        )
        is True
    )

    # confirm panel instance was created and configured
    # hass.data is the only mechanism to get a reference to the created panel instance
    device = hass.data[panel.DOMAIN][panel.CONF_DEVICES]["112233445566"]["panel"]
    await device.update_switch("1", 0)

    # confirm the correct api is used
    assert mock_panel.put_device.call_count == 1
    assert mock_panel.put_zone.call_count == 0

    # confirm the settings are sent to the panel
    assert mock_panel.put_settings.call_args_list[0][1] == {
        "sensors": [{"pin": "1"}, {"pin": "2"}, {"pin": "5"}],
        "actuators": [{"trigger": 0, "pin": "8"}, {"trigger": 1, "pin": "9"}],
        "dht_sensors": [{"poll_interval": 3, "pin": "6"}],
        "ds18b20_sensors": [{"poll_interval": 3, "pin": "7"}],
        "auth_token": "11223344556677889900",
        "blink": True,
        "discovery": True,
        "endpoint": "http://192.168.1.1:8123/api/konnected",
    }

    # confirm the device settings are saved in hass.data
    # This test should not access hass.data since its integration internals
    assert device.stored_configuration == {
        "binary_sensors": {
            "1": {
                "entity_id": "binary_sensor.konnected_445566_zone_1",
                "inverse": False,
                "name": "Konnected 445566 Zone 1",
                "state": None,
                "type": "door",
            },
            "2": {
                "entity_id": "binary_sensor.winder",
                "inverse": True,
                "name": "winder",
                "state": None,
                "type": "window",
            },
            "3": {
                "entity_id": "binary_sensor.konnected_445566_zone_3",
                "inverse": False,
                "name": "Konnected 445566 Zone 3",
                "state": None,
                "type": "door",
            },
        },
        "blink": True,
        "discovery": True,
        "host": "1.2.3.4",
        "panel": device,
        "port": 1234,
        "sensors": [
            {
                "humidity": "sensor.konnected_445566_sensor_4_humidity",
                "name": "Konnected 445566 Sensor 4",
                "poll_interval": 3,
                "temperature": "sensor.konnected_445566_sensor_4_temperature",
                "type": "dht",
                "zone": "4",
            },
            {"name": "temper", "poll_interval": 3, "type": "ds18b20", "zone": "5"},
        ],
        "switches": [
            {
                "activation": "low",
                "entity_id": "switch.switcher",
                "momentary": 50,
                "name": "switcher",
                "pause": 100,
                "repeat": 4,
                "state": None,
                "zone": "out",
            },
            {
                "activation": "high",
                "entity_id": "switch.konnected_445566_actuator_6",
                "momentary": None,
                "name": "Konnected 445566 Actuator 6",
                "pause": None,
                "repeat": None,
                "state": None,
                "zone": "6",
            },
        ],
    }


async def test_create_and_setup_pro(hass: HomeAssistant, mock_panel) -> None:
    """Test that we create a Konnected Pro Panel and save the data."""
    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "11223344556677889900",
            "default_options": config_flow.OPTIONS_SCHEMA({config_flow.CONF_IO: {}}),
        }
    )

    device_options = config_flow.OPTIONS_SCHEMA(
        {
            "io": {
                "2": "Binary Sensor",
                "6": "Binary Sensor",
                "10": "Binary Sensor",
                "11": "Binary Sensor",
                "3": "Digital Sensor",
                "7": "Digital Sensor",
                "4": "Switchable Output",
                "8": "Switchable Output",
                "out1": "Switchable Output",
                "alarm1": "Switchable Output",
            },
            "binary_sensors": [
                {"zone": "2", "type": "door"},
                {"zone": "6", "type": "window", "name": "winder", "inverse": True},
                {"zone": "10", "type": "door"},
                {"zone": "11", "type": "window"},
            ],
            "sensors": [
                {"zone": "3", "type": "dht", "poll_interval": 5},
                {"zone": "7", "type": "ds18b20", "poll_interval": 1, "name": "temper"},
            ],
            "switches": [
                {"zone": "4"},
                {
                    "zone": "8",
                    "name": "switcher",
                    "activation": "low",
                    "momentary": 50,
                    "pause": 100,
                    "repeat": 4,
                },
                {"zone": "out1"},
                {"zone": "alarm1"},
            ],
        }
    )

    entry = MockConfigEntry(
        domain="konnected",
        title="Konnected Pro Alarm Panel",
        data=device_config,
        options=device_options,
    )
    entry.add_to_hass(hass)

    # setup the integration and inspect panel behavior
    assert (
        await async_setup_component(
            hass,
            panel.DOMAIN,
            {
                panel.DOMAIN: {
                    panel.CONF_ACCESS_TOKEN: "arandomstringvalue",
                    panel.CONF_API_HOST: "http://192.168.1.1:8123",
                }
            },
        )
        is True
    )

    # confirm panel instance was created and configured
    # hass.data is the only mechanism to get a reference to the created panel instance
    device = hass.data[panel.DOMAIN][panel.CONF_DEVICES]["112233445566"]["panel"]
    await device.update_switch("2", 1)

    # confirm the correct api is used
    assert mock_panel.put_device.call_count == 0
    assert mock_panel.put_zone.call_count == 1

    # confirm the settings are sent to the panel
    assert mock_panel.put_settings.call_args_list[0][1] == {
        "sensors": [{"zone": "2"}, {"zone": "6"}, {"zone": "10"}, {"zone": "11"}],
        "actuators": [
            {"trigger": 1, "zone": "4"},
            {"trigger": 0, "zone": "8"},
            {"trigger": 1, "zone": "out1"},
            {"trigger": 1, "zone": "alarm1"},
        ],
        "dht_sensors": [{"poll_interval": 5, "zone": "3"}],
        "ds18b20_sensors": [{"poll_interval": 1, "zone": "7"}],
        "auth_token": "11223344556677889900",
        "blink": True,
        "discovery": True,
        "endpoint": "http://192.168.1.1:8123/api/konnected",
    }

    # confirm the device settings are saved in hass.data
    # hass.data should not be accessed in tests as its considered integration internals
    assert device.stored_configuration == {
        "binary_sensors": {
            "10": {
                "entity_id": "binary_sensor.konnected_445566_zone_10",
                "inverse": False,
                "name": "Konnected 445566 Zone 10",
                "state": None,
                "type": "door",
            },
            "11": {
                "entity_id": "binary_sensor.konnected_445566_zone_11",
                "inverse": False,
                "name": "Konnected 445566 Zone 11",
                "state": None,
                "type": "window",
            },
            "2": {
                "entity_id": "binary_sensor.konnected_445566_zone_2",
                "inverse": False,
                "name": "Konnected 445566 Zone 2",
                "state": None,
                "type": "door",
            },
            "6": {
                "entity_id": "binary_sensor.winder",
                "inverse": True,
                "name": "winder",
                "state": None,
                "type": "window",
            },
        },
        "blink": True,
        "discovery": True,
        "host": "1.2.3.4",
        "panel": device,
        "port": 1234,
        "sensors": [
            {
                "humidity": "sensor.konnected_445566_sensor_3_humidity",
                "name": "Konnected 445566 Sensor 3",
                "poll_interval": 5,
                "temperature": "sensor.konnected_445566_sensor_3_temperature",
                "type": "dht",
                "zone": "3",
            },
            {"name": "temper", "poll_interval": 1, "type": "ds18b20", "zone": "7"},
        ],
        "switches": [
            {
                "activation": "high",
                "entity_id": "switch.konnected_445566_actuator_4",
                "momentary": None,
                "name": "Konnected 445566 Actuator 4",
                "pause": None,
                "repeat": None,
                "state": None,
                "zone": "4",
            },
            {
                "activation": "low",
                "entity_id": "switch.switcher",
                "momentary": 50,
                "name": "switcher",
                "pause": 100,
                "repeat": 4,
                "state": None,
                "zone": "8",
            },
            {
                "activation": "high",
                "entity_id": "switch.konnected_445566_actuator_out1",
                "momentary": None,
                "name": "Konnected 445566 Actuator out1",
                "pause": None,
                "repeat": None,
                "state": None,
                "zone": "out1",
            },
            {
                "activation": "high",
                "entity_id": "switch.konnected_445566_actuator_alarm1",
                "momentary": None,
                "name": "Konnected 445566 Actuator alarm1",
                "pause": None,
                "repeat": None,
                "state": None,
                "zone": "alarm1",
            },
        ],
    }


async def test_default_options(hass: HomeAssistant, mock_panel) -> None:
    """Test that we create a Konnected Panel and save the data."""
    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "11223344556677889900",
            "default_options": config_flow.OPTIONS_SCHEMA(
                {
                    "io": {
                        "1": "Binary Sensor",
                        "2": "Binary Sensor",
                        "3": "Binary Sensor",
                        "4": "Digital Sensor",
                        "5": "Digital Sensor",
                        "6": "Switchable Output",
                        "out": "Switchable Output",
                    },
                    "binary_sensors": [
                        {"zone": "1", "type": "door"},
                        {
                            "zone": "2",
                            "type": "window",
                            "name": "winder",
                            "inverse": True,
                        },
                        {"zone": "3", "type": "door"},
                    ],
                    "sensors": [
                        {"zone": "4", "type": "dht"},
                        {"zone": "5", "type": "ds18b20", "name": "temper"},
                    ],
                    "switches": [
                        {
                            "zone": "out",
                            "name": "switcher",
                            "activation": "low",
                            "momentary": 50,
                            "pause": 100,
                            "repeat": 4,
                        },
                        {"zone": "6"},
                    ],
                }
            ),
        }
    )

    entry = MockConfigEntry(
        domain="konnected",
        title="Konnected Alarm Panel",
        data=device_config,
        options={},
    )
    entry.add_to_hass(hass)

    # override get_status to reflect non-pro board
    mock_panel.get_status.return_value = {
        "hwVersion": "2.3.0",
        "swVersion": "2.3.1",
        "heap": 10000,
        "uptime": 12222,
        "ip": "192.168.1.90",
        "port": 9123,
        "sensors": [],
        "actuators": [],
        "dht_sensors": [],
        "ds18b20_sensors": [],
        "mac": "11:22:33:44:55:66",
        "settings": {},
    }

    # setup the integration and inspect panel behavior
    assert (
        await async_setup_component(
            hass,
            panel.DOMAIN,
            {
                panel.DOMAIN: {
                    panel.CONF_ACCESS_TOKEN: "arandomstringvalue",
                    panel.CONF_API_HOST: "http://192.168.1.1:8123",
                }
            },
        )
        is True
    )

    # confirm panel instance was created and configured.
    # hass.data is the only mechanism to get a reference to the created panel instance
    device = hass.data[panel.DOMAIN][panel.CONF_DEVICES]["112233445566"]["panel"]
    await device.update_switch("1", 0)

    # confirm the correct api is used
    assert mock_panel.put_device.call_count == 1
    assert mock_panel.put_zone.call_count == 0

    # confirm the settings are sent to the panel
    assert mock_panel.put_settings.call_args_list[0][1] == {
        "sensors": [{"pin": "1"}, {"pin": "2"}, {"pin": "5"}],
        "actuators": [{"trigger": 0, "pin": "8"}, {"trigger": 1, "pin": "9"}],
        "dht_sensors": [{"poll_interval": 3, "pin": "6"}],
        "ds18b20_sensors": [{"poll_interval": 3, "pin": "7"}],
        "auth_token": "11223344556677889900",
        "blink": True,
        "discovery": True,
        "endpoint": "http://192.168.1.1:8123/api/konnected",
    }

    # confirm the device settings are saved in hass.data
    # This test should not access hass.data since its integration internals
    assert device.stored_configuration == {
        "binary_sensors": {
            "1": {
                "entity_id": "binary_sensor.konnected_445566_zone_1",
                "inverse": False,
                "name": "Konnected 445566 Zone 1",
                "state": None,
                "type": "door",
            },
            "2": {
                "entity_id": "binary_sensor.winder",
                "inverse": True,
                "name": "winder",
                "state": None,
                "type": "window",
            },
            "3": {
                "entity_id": "binary_sensor.konnected_445566_zone_3",
                "inverse": False,
                "name": "Konnected 445566 Zone 3",
                "state": None,
                "type": "door",
            },
        },
        "blink": True,
        "discovery": True,
        "host": "1.2.3.4",
        "panel": device,
        "port": 1234,
        "sensors": [
            {
                "humidity": "sensor.konnected_445566_sensor_4_humidity",
                "name": "Konnected 445566 Sensor 4",
                "poll_interval": 3,
                "temperature": "sensor.konnected_445566_sensor_4_temperature",
                "type": "dht",
                "zone": "4",
            },
            {"name": "temper", "poll_interval": 3, "type": "ds18b20", "zone": "5"},
        ],
        "switches": [
            {
                "activation": "low",
                "entity_id": "switch.switcher",
                "momentary": 50,
                "name": "switcher",
                "pause": 100,
                "repeat": 4,
                "state": None,
                "zone": "out",
            },
            {
                "activation": "high",
                "entity_id": "switch.konnected_445566_actuator_6",
                "momentary": None,
                "name": "Konnected 445566 Actuator 6",
                "pause": None,
                "repeat": None,
                "state": None,
                "zone": "6",
            },
        ],
    }


async def test_connect_retry(hass: HomeAssistant, mock_panel) -> None:
    """Test that we create a Konnected Panel and save the data."""
    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "11223344556677889900",
            "default_options": config_flow.OPTIONS_SCHEMA(
                {
                    "io": {
                        "1": "Binary Sensor",
                        "2": "Binary Sensor",
                        "3": "Binary Sensor",
                        "4": "Digital Sensor",
                        "5": "Digital Sensor",
                        "6": "Switchable Output",
                        "out": "Switchable Output",
                    },
                    "binary_sensors": [
                        {"zone": "1", "type": "door"},
                        {
                            "zone": "2",
                            "type": "window",
                            "name": "winder",
                            "inverse": True,
                        },
                        {"zone": "3", "type": "door"},
                    ],
                    "sensors": [
                        {"zone": "4", "type": "dht"},
                        {"zone": "5", "type": "ds18b20", "name": "temper"},
                    ],
                    "switches": [
                        {
                            "zone": "out",
                            "name": "switcher",
                            "activation": "low",
                            "momentary": 50,
                            "pause": 100,
                            "repeat": 4,
                        },
                        {"zone": "6"},
                    ],
                }
            ),
        }
    )

    entry = MockConfigEntry(
        domain="konnected",
        title="Konnected Alarm Panel",
        data=device_config,
        options={},
    )
    entry.add_to_hass(hass)

    # fail first 2 attempts, and succeed the third
    mock_panel.get_status.side_effect = [
        mock_panel.ClientError,
        mock_panel.ClientError,
        {
            "hwVersion": "2.3.0",
            "swVersion": "2.3.1",
            "heap": 10000,
            "uptime": 12222,
            "ip": "192.168.1.90",
            "port": 9123,
            "sensors": [],
            "actuators": [],
            "dht_sensors": [],
            "ds18b20_sensors": [],
            "mac": "11:22:33:44:55:66",
            "model": "Konnected Pro",
            "settings": {},
        },
    ]

    # setup the integration and inspect panel behavior
    assert (
        await async_setup_component(
            hass,
            panel.DOMAIN,
            {
                panel.DOMAIN: {
                    panel.CONF_ACCESS_TOKEN: "arandomstringvalue",
                    panel.CONF_API_HOST: "http://192.168.1.1:8123",
                }
            },
        )
        is True
    )

    # confirm switch is unavailable after initial attempt
    await hass.async_block_till_done()
    assert hass.states.get("switch.konnected_445566_actuator_6").state == "unavailable"

    # confirm switch is unavailable after second attempt
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()
    await async_update_entity(hass, "switch.konnected_445566_actuator_6")
    assert hass.states.get("switch.konnected_445566_actuator_6").state == "unavailable"

    # confirm switch is available after third attempt
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=21))
    await hass.async_block_till_done()
    await async_update_entity(hass, "switch.konnected_445566_actuator_6")
    assert hass.states.get("switch.konnected_445566_actuator_6").state == "off"
