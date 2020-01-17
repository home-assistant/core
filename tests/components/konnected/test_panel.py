"""Test Konnected setup process."""
from unittest.mock import patch

from homeassistant.components.konnected import config_flow, panel

from tests.common import MockConfigEntry, mock_coro


async def test_create_and_setup(hass):
    """Test that we create a Konnected Panel and save the data."""
    device_config = config_flow.DEVICE_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
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
        domain="konnected", title="Konnected Alarm Panel", data=device_config
    )
    entry.add_to_hass(hass)
    hass.data[panel.DOMAIN] = {
        panel.CONF_ACCESS_TOKEN: "some_token",
        panel.CONF_API_HOST: "192.168.1.1",
    }

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.ClientError = config_flow.CannotConnect
        mock_panel.get_status.return_value = mock_coro(
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
                "settings": {},
            }
        )
        mock_panel.put_settings.return_value = mock_coro()
        mock_panel.put_device.return_value = mock_coro()
        mock_panel.put_zone.return_value = mock_coro()

        device = panel.AlarmPanel(hass, entry)
        await device.async_save_data()
        await device.async_connect()
        await device.update_switch("1", 0)

    # confirm the correct api is used
    # pylint: disable=no-member
    assert device.client.put_device.call_count == 1
    assert device.client.put_zone.call_count == 0

    # confirm the settings are sent to the panel
    # pylint: disable=no-member
    assert device.client.put_settings.call_args_list[0][1] == {
        "sensors": [{"pin": "1"}, {"pin": "2"}, {"pin": "5"}],
        "actuators": [{"trigger": 0, "pin": "8"}, {"trigger": 1, "pin": "9"}],
        "dht_sensors": [{"poll_interval": 3, "pin": "6"}],
        "ds18b20_sensors": [{"pin": "7"}],
        "auth_token": "some_token",
        "blink": True,
        "discovery": True,
        "endpoint": "192.168.1.1/api/konnected",
    }

    # confirm the device settings are saved in hass.data
    assert hass.data[panel.DOMAIN][panel.CONF_DEVICES] == {
        "112233445566": {
            "binary_sensors": {
                "1": {
                    "inverse": False,
                    "name": "Konnected 445566 Zone 1",
                    "state": None,
                    "type": "door",
                },
                "2": {
                    "inverse": True,
                    "name": "winder",
                    "state": None,
                    "type": "window",
                },
                "3": {
                    "inverse": False,
                    "name": "Konnected 445566 Zone 3",
                    "state": None,
                    "type": "door",
                },
            },
            "blink": True,
            "panel": device,
            "discovery": True,
            "host": "1.2.3.4",
            "port": 1234,
            "sensors": [
                {
                    "name": "Konnected 445566 Sensor 4",
                    "poll_interval": 3,
                    "type": "dht",
                    "zone": "4",
                },
                {"name": "temper", "poll_interval": 3, "type": "ds18b20", "zone": "5"},
            ],
            "switches": [
                {
                    "activation": "low",
                    "momentary": 50,
                    "name": "switcher",
                    "pause": 100,
                    "repeat": 4,
                    "state": None,
                    "zone": "out",
                },
                {
                    "activation": "high",
                    "momentary": None,
                    "name": "Konnected 445566 Actuator 6",
                    "pause": None,
                    "repeat": None,
                    "state": None,
                    "zone": "6",
                },
            ],
        }
    }


async def test_create_and_setup_pro(hass):
    """Test that we create a Konnected Pro Panel and save the data."""
    device_config = config_flow.DEVICE_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "binary_sensors": [
                {"zone": "2", "type": "door"},
                {"zone": "6", "type": "window", "name": "winder", "inverse": True},
                {"zone": "10", "type": "door"},
            ],
            "sensors": [
                {"zone": "3", "type": "dht"},
                {"zone": "7", "type": "ds18b20", "name": "temper"},
                {"zone": "11", "type": "dht", "poll_interval": 5},
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
        domain="konnected", title="Konnected Pro Alarm Panel", data=device_config
    )
    entry.add_to_hass(hass)
    hass.data[panel.DOMAIN] = {
        panel.CONF_ACCESS_TOKEN: "some_token",
        panel.CONF_API_HOST: "192.168.1.1",
    }

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.ClientError = config_flow.CannotConnect
        mock_panel.get_status.return_value = mock_coro(
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
                "model": "Konnected Pro",  # `model` field only included in pro
                "settings": {},
            }
        )
        mock_panel.put_settings.return_value = mock_coro()
        mock_panel.put_device.return_value = mock_coro()
        mock_panel.put_zone.return_value = mock_coro()

        device = panel.AlarmPanel(hass, entry)
        await device.async_save_data()
        await device.async_connect()
        await device.update_switch("2", 1)

    # confirm the correct api is used
    # pylint: disable=no-member
    assert device.client.put_device.call_count == 0
    assert device.client.put_zone.call_count == 1

    # confirm the settings are sent to the panel
    # pylint: disable=no-member
    assert device.client.put_settings.call_args_list[0][1] == {
        "sensors": [{"zone": "2"}, {"zone": "6"}, {"zone": "10"}],
        "actuators": [
            {"trigger": 1, "zone": "4"},
            {"trigger": 0, "zone": "8"},
            {"trigger": 1, "zone": "out1"},
            {"trigger": 1, "zone": "alarm1"},
        ],
        "dht_sensors": [
            {"poll_interval": 3, "zone": "3"},
            {"poll_interval": 5, "zone": "11"},
        ],
        "ds18b20_sensors": [{"zone": "7"}],
        "auth_token": "some_token",
        "blink": True,
        "discovery": True,
        "endpoint": "192.168.1.1/api/konnected",
    }

    # confirm the device settings are saved in hass.data
    assert hass.data[panel.DOMAIN][panel.CONF_DEVICES] == {
        "112233445566": {
            "binary_sensors": {
                "10": {
                    "inverse": False,
                    "name": "Konnected 445566 Zone 10",
                    "state": None,
                    "type": "door",
                },
                "2": {
                    "inverse": False,
                    "name": "Konnected 445566 Zone 2",
                    "state": None,
                    "type": "door",
                },
                "6": {
                    "inverse": True,
                    "name": "winder",
                    "state": None,
                    "type": "window",
                },
            },
            "blink": True,
            "panel": device,
            "discovery": True,
            "host": "1.2.3.4",
            "port": 1234,
            "sensors": [
                {
                    "name": "Konnected 445566 Sensor 3",
                    "poll_interval": 3,
                    "type": "dht",
                    "zone": "3",
                },
                {"name": "temper", "poll_interval": 3, "type": "ds18b20", "zone": "7"},
                {
                    "name": "Konnected 445566 Sensor 11",
                    "poll_interval": 5,
                    "type": "dht",
                    "zone": "11",
                },
            ],
            "switches": [
                {
                    "activation": "high",
                    "momentary": None,
                    "name": "Konnected 445566 Actuator 4",
                    "pause": None,
                    "repeat": None,
                    "state": None,
                    "zone": "4",
                },
                {
                    "activation": "low",
                    "momentary": 50,
                    "name": "switcher",
                    "pause": 100,
                    "repeat": 4,
                    "state": None,
                    "zone": "8",
                },
                {
                    "activation": "high",
                    "momentary": None,
                    "name": "Konnected 445566 Actuator out1",
                    "pause": None,
                    "repeat": None,
                    "state": None,
                    "zone": "out1",
                },
                {
                    "activation": "high",
                    "momentary": None,
                    "name": "Konnected 445566 Actuator alarm1",
                    "pause": None,
                    "repeat": None,
                    "state": None,
                    "zone": "alarm1",
                },
            ],
        }
    }
