"""Test Konnected setup process."""
from unittest.mock import patch

from homeassistant.components import konnected
from homeassistant.components.konnected import config_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a Konnected panel."""
    with patch.object(hass, "config_entries") as mock_config_entries, patch.object(
        konnected, "configured_devices", return_value=[]
    ):
        assert await async_setup_component(hass, konnected.DOMAIN, {}) is True

    # No flows started
    assert len(mock_config_entries.flow.mock_calls) == 0

    # Default access token used
    assert hass.data[konnected.DOMAIN][konnected.CONF_ACCESS_TOKEN] is not None
    assert hass.data[konnected.DOMAIN][konnected.CONF_API_HOST] is None
    assert konnected.YAML_CONFIGS not in hass.data[konnected.DOMAIN]


async def test_setup_defined_hosts_known_auth(hass):
    """Test we don't initiate a config entry if configured panel is known."""
    with patch.object(hass, "config_entries") as mock_config_entries, patch.object(
        konnected, "configured_devices", return_value=["aabbccddeeff", "112233445566"]
    ):
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
                            },
                        ],
                    }
                },
            )
            is True
        )

    # Flow started for discovered panel
    assert len(mock_config_entries.flow.mock_calls) == 0


async def test_setup_defined_hosts_no_known_auth(hass):
    """Test we initiate config entry if config panel is not known."""
    with patch.object(hass, "config_entries") as mock_config_entries, patch.object(
        konnected, "configured_devices", return_value=[]
    ):
        mock_config_entries.flow.async_init.return_value = mock_coro()
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
    assert len(mock_config_entries.flow.mock_calls) == 1
    assert mock_config_entries.flow.mock_calls[0][2]["data"] == {
        config_flow.CONF_ID: "aabbccddeeff",
        config_flow.CONF_BLINK: True,
        config_flow.CONF_DISCOVERY: True,
    }


async def test_config_passed_to_config_entry(hass):
    """Test that configured options for a host are loaded via config entry."""
    entry = MockConfigEntry(
        domain=konnected.DOMAIN,
        data={config_flow.CONF_ID: "aabbccddeeff", config_flow.CONF_HOST: "0.0.0.0"},
    )
    entry.add_to_hass(hass)
    with patch.object(konnected, "AlarmPanel") as mock_panel:
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

    assert len(mock_panel.mock_calls) == 2
    p_hass, p_entry = mock_panel.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry is entry


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=konnected.DOMAIN, data={konnected.CONF_ID: "aabbccddeeff"}
    )
    entry.add_to_hass(hass)

    with patch.object(konnected, "AlarmPanel") as mock_panel:

        def mock_constructor(hass, entry):
            """Fake the panel constructor."""
            return mock_panel

        def save_data():
            hass.data[konnected.DOMAIN]["devices"]["aabbccddeeff"] = {"some": "thing"}

        mock_panel.side_effect = mock_constructor
        mock_panel.async_save_data.side_effect = save_data
        mock_panel.async_save_data.return_value = mock_coro()
        mock_panel.async_connect.return_value = mock_coro()
        assert await async_setup_component(hass, konnected.DOMAIN, {}) is True

    assert hass.data[konnected.DOMAIN]["devices"].get("aabbccddeeff") is not None

    assert await konnected.async_unload_entry(hass, entry)
    assert hass.data[konnected.DOMAIN]["devices"] == {}


async def test_api(hass, aiohttp_client):
    """Test callback view."""
    await async_setup_component(hass, "http", {"http": {}})

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

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
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

        assert (
            await async_setup_component(
                hass,
                konnected.DOMAIN,
                {konnected.DOMAIN: {konnected.CONF_ACCESS_TOKEN: "abcdefgh"}},
            )
            is True
        )

    client = await aiohttp_client(hass.http.app)

    # Test the get endpoint for switch status polling
    resp = await client.get("/api/konnected")
    assert resp.status == 404  # no device provided

    resp = await client.get("/api/konnected/223344556677")
    assert resp.status == 404  # unknown device provided

    resp = await client.get("/api/konnected/device/112233445566")
    assert resp.status == 404  # no zone provided
    result = await resp.json()
    assert result == {"message": "Switch on zone or pin unknown not configured"}

    resp = await client.get("/api/konnected/device/112233445566?zone=8")
    assert resp.status == 404  # invalid zone
    result = await resp.json()
    assert result == {"message": "Switch on zone or pin 8 not configured"}

    resp = await client.get("/api/konnected/device/112233445566?pin=12")
    assert resp.status == 404  # invalid pin
    result = await resp.json()
    assert result == {"message": "Switch on zone or pin 12 not configured"}

    resp = await client.get("/api/konnected/device/112233445566?zone=out")
    assert resp.status == 200
    result = await resp.json()
    assert result == {"state": 1, "zone": "out"}

    resp = await client.get("/api/konnected/device/112233445566?pin=8")
    assert resp.status == 200
    result = await resp.json()
    assert result == {"state": 1, "pin": "8"}

    # Test the post endpoint for sensor updates
    resp = await client.post("/api/konnected/device", json={"zone": "1", "state": 1})
    assert resp.status == 404

    resp = await client.post(
        "/api/konnected/device/112233445566", json={"zone": "1", "state": 1}
    )
    assert resp.status == 401
    result = await resp.json()
    assert result == {"message": "unauthorized"}

    resp = await client.post(
        "/api/konnected/device/223344556677",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == 400

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "15", "state": 1},
    )
    assert resp.status == 400
    result = await resp.json()
    assert result == {"message": "unregistered sensor/actuator"}

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == 200
    result = await resp.json()
    assert result == {"message": "ok"}

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "4", "temp": 22, "humi": 20},
    )
    assert resp.status == 200
    result = await resp.json()
    assert result == {"message": "ok"}

    # Test the put endpoint for sensor updates
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == 200
    result = await resp.json()
    assert result == {"message": "ok"}


async def test_state_updates(hass, aiohttp_client):
    """Test callback view."""
    await async_setup_component(hass, "http", {"http": {}})

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

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
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

        assert (
            await async_setup_component(
                hass,
                konnected.DOMAIN,
                {konnected.DOMAIN: {konnected.CONF_ACCESS_TOKEN: "abcdefgh"}},
            )
            is True
        )

    client = await aiohttp_client(hass.http.app)

    # Test updating a binary sensor
    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 0},
    )
    assert resp.status == 200
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.konnected_445566_zone_1").state == "off"

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "1", "state": 1},
    )
    assert resp.status == 200
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
    assert resp.status == 200
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
    assert resp.status == 200
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
    assert resp.status == 200
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.temper_temperature").state == "32.0"

    resp = await client.post(
        "/api/konnected/device/112233445566",
        headers={"Authorization": "Bearer abcdefgh"},
        json={"zone": "5", "temp": 42, "addr": 1},
    )
    assert resp.status == 200
    result = await resp.json()
    assert result == {"message": "ok"}
    await hass.async_block_till_done()
    assert hass.states.get("sensor.temper_temperature").state == "42.0"
