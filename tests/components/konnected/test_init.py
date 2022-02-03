"""Test Konnected setup process."""
from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.components import konnected
from homeassistant.components.konnected import config_flow
from homeassistant.config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


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
            "settings": {},
        }
        yield konn_client


async def test_config_schema(hass):
    """Test that config schema is imported properly."""
    config = {
        konnected.DOMAIN: {
            konnected.CONF_API_HOST: "http://1.1.1.1:8888",
            konnected.CONF_ACCESS_TOKEN: "abcdefgh",
            konnected.CONF_DEVICES: [{konnected.CONF_ID: "aabbccddeeff"}],
        }
    }
    assert konnected.CONFIG_SCHEMA(config) == {
        "konnected": {
            "access_token": "abcdefgh",
            "api_host": "http://1.1.1.1:8888",
            "devices": [
                {
                    "default_options": {
                        "blink": True,
                        "api_host": "http://1.1.1.1:8888",
                        "discovery": True,
                        "io": {
                            "1": "Disabled",
                            "10": "Disabled",
                            "11": "Disabled",
                            "12": "Disabled",
                            "2": "Disabled",
                            "3": "Disabled",
                            "4": "Disabled",
                            "5": "Disabled",
                            "6": "Disabled",
                            "7": "Disabled",
                            "8": "Disabled",
                            "9": "Disabled",
                            "alarm1": "Disabled",
                            "alarm2_out2": "Disabled",
                            "out": "Disabled",
                            "out1": "Disabled",
                        },
                    },
                    "id": "aabbccddeeff",
                }
            ],
        }
    }

    # check with host info
    config = {
        konnected.DOMAIN: {
            konnected.CONF_ACCESS_TOKEN: "abcdefgh",
            konnected.CONF_DEVICES: [
                {konnected.CONF_ID: "aabbccddeeff", "host": "192.168.1.1", "port": 1234}
            ],
        }
    }
    assert konnected.CONFIG_SCHEMA(config) == {
        "konnected": {
            "access_token": "abcdefgh",
            "devices": [
                {
                    "default_options": {
                        "blink": True,
                        "api_host": "",
                        "discovery": True,
                        "io": {
                            "1": "Disabled",
                            "10": "Disabled",
                            "11": "Disabled",
                            "12": "Disabled",
                            "2": "Disabled",
                            "3": "Disabled",
                            "4": "Disabled",
                            "5": "Disabled",
                            "6": "Disabled",
                            "7": "Disabled",
                            "8": "Disabled",
                            "9": "Disabled",
                            "alarm1": "Disabled",
                            "alarm2_out2": "Disabled",
                            "out": "Disabled",
                            "out1": "Disabled",
                        },
                    },
                    "id": "aabbccddeeff",
                    "host": "192.168.1.1",
                    "port": 1234,
                }
            ],
        }
    }

    # check pin to zone and multiple output
    config = {
        konnected.DOMAIN: {
            konnected.CONF_ACCESS_TOKEN: "abcdefgh",
            konnected.CONF_DEVICES: [
                {
                    konnected.CONF_ID: "aabbccddeeff",
                    "binary_sensors": [
                        {"pin": 2, "type": "door"},
                        {"zone": 1, "type": "door"},
                    ],
                    "switches": [
                        {
                            "zone": 3,
                            "name": "Beep Beep",
                            "momentary": 65,
                            "pause": 55,
                            "repeat": 4,
                        },
                        {
                            "zone": 3,
                            "name": "Warning",
                            "momentary": 100,
                            "pause": 100,
                            "repeat": -1,
                        },
                    ],
                }
            ],
        }
    }
    assert konnected.CONFIG_SCHEMA(config) == {
        "konnected": {
            "access_token": "abcdefgh",
            "devices": [
                {
                    "default_options": {
                        "blink": True,
                        "api_host": "",
                        "discovery": True,
                        "io": {
                            "1": "Binary Sensor",
                            "10": "Disabled",
                            "11": "Disabled",
                            "12": "Disabled",
                            "2": "Binary Sensor",
                            "3": "Switchable Output",
                            "4": "Disabled",
                            "5": "Disabled",
                            "6": "Disabled",
                            "7": "Disabled",
                            "8": "Disabled",
                            "9": "Disabled",
                            "alarm1": "Disabled",
                            "alarm2_out2": "Disabled",
                            "out": "Disabled",
                            "out1": "Disabled",
                        },
                        "binary_sensors": [
                            {"inverse": False, "type": "door", "zone": "2"},
                            {"inverse": False, "type": "door", "zone": "1"},
                        ],
                        "switches": [
                            {
                                "zone": "3",
                                "activation": "high",
                                "name": "Beep Beep",
                                "momentary": 65,
                                "pause": 55,
                                "repeat": 4,
                            },
                            {
                                "zone": "3",
                                "activation": "high",
                                "name": "Warning",
                                "momentary": 100,
                                "pause": 100,
                                "repeat": -1,
                            },
                        ],
                    },
                    "id": "aabbccddeeff",
                }
            ],
        }
    }


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a Konnected panel."""
    assert await async_setup_component(hass, konnected.DOMAIN, {})

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    # Nothing saved from configuration.yaml
    assert hass.data[konnected.DOMAIN][konnected.CONF_ACCESS_TOKEN] is None
    assert hass.data[konnected.DOMAIN][konnected.CONF_API_HOST] is None
    assert konnected.YAML_CONFIGS not in hass.data[konnected.DOMAIN]


async def test_setup_defined_hosts_known_auth(hass, mock_panel):
    """Test we don't initiate a config entry if configured panel is known."""
    MockConfigEntry(
        domain="konnected",
        unique_id="112233445566",
        data={"host": "0.0.0.0", "id": "112233445566"},
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="konnected",
        unique_id="aabbccddeeff",
        data={"host": "1.2.3.4", "id": "aabbccddeeff"},
    ).add_to_hass(hass)

    assert (
        await async_setup_component(
            hass,
            konnected.DOMAIN,
            {
                konnected.DOMAIN: {
                    konnected.CONF_ACCESS_TOKEN: "abcdefgh",
                    konnected.CONF_DEVICES: [
                        {
                            config_flow.CONF_ID: "aabbccddeeff",
                            config_flow.CONF_HOST: "0.0.0.0",
                            config_flow.CONF_PORT: 1234,
                        }
                    ],
                }
            },
        )
        is True
    )

    assert hass.data[konnected.DOMAIN][konnected.CONF_ACCESS_TOKEN] == "abcdefgh"
    assert konnected.YAML_CONFIGS not in hass.data[konnected.DOMAIN]

    # Flow aborted
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_setup_defined_hosts_no_known_auth(hass):
    """Test we initiate config entry if config panel is not known."""
    assert (
        await async_setup_component(
            hass,
            konnected.DOMAIN,
            {
                konnected.DOMAIN: {
                    konnected.CONF_ACCESS_TOKEN: "abcdefgh",
                    konnected.CONF_DEVICES: [{konnected.CONF_ID: "aabbccddeeff"}],
                }
            },
        )
        is True
    )

    # Flow started for discovered bridge
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_setup_multiple(hass):
    """Test we initiate config entry for multiple panels."""
    assert (
        await async_setup_component(
            hass,
            konnected.DOMAIN,
            {
                konnected.DOMAIN: {
                    konnected.CONF_ACCESS_TOKEN: "arandomstringvalue",
                    konnected.CONF_API_HOST: "http://192.168.86.32:8123",
                    konnected.CONF_DEVICES: [
                        {
                            konnected.CONF_ID: "aabbccddeeff",
                            "binary_sensors": [
                                {"zone": 4, "type": "motion", "name": "Hallway Motion"},
                                {
                                    "zone": 5,
                                    "type": "window",
                                    "name": "Master Bedroom Window",
                                },
                                {
                                    "zone": 6,
                                    "type": "window",
                                    "name": "Downstairs Windows",
                                },
                            ],
                            "switches": [{"zone": "out", "name": "siren"}],
                        },
                        {
                            konnected.CONF_ID: "445566778899",
                            "binary_sensors": [
                                {"zone": 1, "type": "motion", "name": "Front"},
                                {"zone": 2, "type": "window", "name": "Back"},
                            ],
                            "switches": [
                                {
                                    "zone": "out",
                                    "name": "Buzzer",
                                    "momentary": 65,
                                    "pause": 55,
                                    "repeat": 4,
                                }
                            ],
                        },
                    ],
                }
            },
        )
        is True
    )

    # Flow started for discovered bridge
    assert len(hass.config_entries.flow.async_progress()) == 2

    # Globals saved
    assert (
        hass.data[konnected.DOMAIN][konnected.CONF_ACCESS_TOKEN] == "arandomstringvalue"
    )
    assert (
        hass.data[konnected.DOMAIN][konnected.CONF_API_HOST]
        == "http://192.168.86.32:8123"
    )


async def test_config_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(
        domain=konnected.DOMAIN,
        data={config_flow.CONF_ID: "aabbccddeeff", config_flow.CONF_HOST: "0.0.0.0"},
    )
    entry.add_to_hass(hass)
    with patch.object(konnected, "AlarmPanel", autospec=True) as mock_int:
        assert (
            await async_setup_component(
                hass,
                konnected.DOMAIN,
                {
                    konnected.DOMAIN: {
                        konnected.CONF_ACCESS_TOKEN: "abcdefgh",
                        konnected.CONF_DEVICES: [{konnected.CONF_ID: "aabbccddeeff"}],
                    }
                },
            )
            is True
        )

    assert len(mock_int.mock_calls) == 3
    p_hass, p_entry = mock_int.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry is entry


async def test_unload_entry(hass, mock_panel):
    """Test being able to unload an entry."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )
    entry = MockConfigEntry(
        domain=konnected.DOMAIN, data={konnected.CONF_ID: "aabbccddeeff"}
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, konnected.DOMAIN, {}) is True
    assert hass.data[konnected.DOMAIN]["devices"].get("aabbccddeeff") is not None
    assert await konnected.async_unload_entry(hass, entry)
    assert hass.data[konnected.DOMAIN]["devices"] == {}


async def test_api(hass, hass_client_no_auth, mock_panel):
    """Test callback view."""
    await async_setup_component(hass, "http", {"http": {}})

    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "abcdefgh",
            "api_host": "http://192.168.86.32:8123",
            "default_options": config_flow.OPTIONS_SCHEMA({config_flow.CONF_IO: {}}),
        }
    )

    device_options = config_flow.OPTIONS_SCHEMA(
        {
            "api_host": "http://192.168.86.32:8123",
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

    assert (
        await async_setup_component(
            hass,
            konnected.DOMAIN,
            {konnected.DOMAIN: {konnected.CONF_ACCESS_TOKEN: "globaltoken"}},
        )
        is True
    )

    client = await hass_client_no_auth()

    # Test the get endpoint for switch status polling
    resp = await client.get("/api/konnected")
    assert resp.status == HTTPStatus.NOT_FOUND  # no device provided

    resp = await client.get("/api/konnected/223344556677")
    assert resp.status == HTTPStatus.NOT_FOUND  # unknown device provided

    resp = await client.get("/api/konnected/device/112233445566")
    assert resp.status == HTTPStatus.NOT_FOUND  # no zone provided
    result = await resp.json()
    assert result == {"message": "Switch on zone or pin unknown not configured"}

    resp = await client.get("/api/konnected/device/112233445566?zone=8")
    assert resp.status == HTTPStatus.NOT_FOUND  # invalid zone
    result = await resp.json()
    assert result == {"message": "Switch on zone or pin 8 not configured"}

    resp = await client.get("/api/konnected/device/112233445566?pin=12")
    assert resp.status == HTTPStatus.NOT_FOUND  # invalid pin
    result = await resp.json()
    assert result == {"message": "Switch on zone or pin 12 not configured"}

    resp = await client.get("/api/konnected/device/112233445566?zone=out")
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"state": 1, "zone": "out"}

    resp = await client.get("/api/konnected/device/112233445566?pin=8")
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"state": 1, "pin": "8"}

    # Test the post endpoint for sensor updates
    resp = await client.post("/api/konnected/device", json={"zone": "1", "state": 1})
    assert resp.status == HTTPStatus.NOT_FOUND

    resp = await client.post(
        "/api/konnected/device/112233445566", json={"zone": "1", "state": 1}
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED
    result = await resp.json()
    assert result == {"message": "unauthorized"}

    resp = await client.post(
        "/api/konnected/device/223344556677",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == HTTPStatus.BAD_REQUEST

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "15", "state": 1},
    )
    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result == {"message": "unregistered sensor/actuator"}

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer globaltoken"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "4", "temp": 22, "humi": 20},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}

    # Test the put endpoint for sensor updates
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}


async def test_state_updates_zone(hass, hass_client_no_auth, mock_panel):
    """Test callback view."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "abcdefgh",
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

    # Add empty data field to ensure we process it correctly (possible if entry is ignored)
    entry = MockConfigEntry(domain="konnected", title="Konnected Alarm Panel", data={})
    entry.add_to_hass(hass)

    assert (
        await async_setup_component(
            hass,
            konnected.DOMAIN,
            {konnected.DOMAIN: {konnected.CONF_ACCESS_TOKEN: "1122334455"}},
        )
        is True
    )

    client = await hass_client_no_auth()

    # Test updating a binary sensor
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 0},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.konnected_445566_zone_1").state == "off"

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.konnected_445566_zone_1").state == "on"

    # Test updating sht sensor
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "4", "temp": 22, "humi": 20},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.konnected_445566_sensor_4_humidity").state == "20"
    assert (
        hass.states.get("sensor.konnected_445566_sensor_4_temperature").state == "22.0"
    )

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "4", "temp": 25, "humi": 23},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.konnected_445566_sensor_4_humidity").state == "23"
    assert (
        hass.states.get("sensor.konnected_445566_sensor_4_temperature").state == "25.0"
    )

    # Test updating ds sensor
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "5", "temp": 32, "addr": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.temper_temperature").state == "32.0"

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "5", "temp": 42, "addr": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.temper_temperature").state == "42.0"


async def test_state_updates_pin(hass, hass_client_no_auth, mock_panel):
    """Test callback view."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected",
            "access_token": "abcdefgh",
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

    # Add empty data field to ensure we process it correctly (possible if entry is ignored)
    entry = MockConfigEntry(
        domain="konnected",
        title="Konnected Alarm Panel",
        data={},
    )
    entry.add_to_hass(hass)

    assert (
        await async_setup_component(
            hass,
            konnected.DOMAIN,
            {konnected.DOMAIN: {konnected.CONF_ACCESS_TOKEN: "1122334455"}},
        )
        is True
    )

    client = await hass_client_no_auth()

    # Test updating a binary sensor
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"pin": "1", "state": 0},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.konnected_445566_zone_1").state == "off"

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"pin": "1", "state": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.konnected_445566_zone_1").state == "on"

    # Test updating sht sensor
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"pin": "6", "temp": 22, "humi": 20},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.konnected_445566_sensor_4_humidity").state == "20"
    assert (
        hass.states.get("sensor.konnected_445566_sensor_4_temperature").state == "22.0"
    )

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"pin": "6", "temp": 25, "humi": 23},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.konnected_445566_sensor_4_humidity").state == "23"
    assert (
        hass.states.get("sensor.konnected_445566_sensor_4_temperature").state == "25.0"
    )

    # Test updating ds sensor
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"pin": "7", "temp": 32, "addr": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.temper_temperature").state == "32.0"

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"pin": "7", "temp": 42, "addr": 1},
    )
    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.temper_temperature").state == "42.0"
