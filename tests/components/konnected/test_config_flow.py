"""Tests for Konnected Alarm Panel config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components import konnected
from homeassistant.components.konnected import config_flow

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
        yield konn_client


async def test_flow_works(hass, mock_panel):
    """Test config flow ."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "model": "Konnected",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"port": 1234, "host": "1.2.3.4"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "model": "Konnected Alarm Panel",
        "id": "112233445566",
        "host": "1.2.3.4",
        "port": 1234,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    assert result["data"]["host"] == "1.2.3.4"
    assert result["data"]["port"] == 1234
    assert result["data"]["model"] == "Konnected"
    assert len(result["data"]["access_token"]) == 20  # confirm generated token size
    assert result["data"]["default_options"] == config_flow.OPTIONS_SCHEMA(
        {config_flow.CONF_IO: {}}
    )


async def test_pro_flow_works(hass, mock_panel):
    """Test config flow ."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # pro uses chipId instead of MAC as unique id
    mock_panel.get_status.return_value = {
        "chipId": "1234567",
        "mac": "11:22:33:44:55:66",
        "model": "Konnected Pro",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"port": 1234, "host": "1.2.3.4"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "model": "Konnected Alarm Panel Pro",
        "id": "1234567",
        "host": "1.2.3.4",
        "port": 1234,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    assert result["data"]["host"] == "1.2.3.4"
    assert result["data"]["port"] == 1234
    assert result["data"]["model"] == "Konnected Pro"
    assert len(result["data"]["access_token"]) == 20  # confirm generated token size
    assert result["data"]["default_options"] == config_flow.OPTIONS_SCHEMA(
        {config_flow.CONF_IO: {}}
    )


async def test_ssdp(hass, mock_panel):
    """Test a panel being discovered."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "model": "Konnected",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "ssdp_location": "http://1.2.3.4:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "model": "Konnected Alarm Panel",
        "id": "112233445566",
        "host": "1.2.3.4",
        "port": 1234,
    }


async def test_import_no_host_user_finish(hass, mock_panel):
    """Test importing a panel with no host info."""
    mock_panel.get_status.return_value = {
        "mac": "aa:bb:cc:dd:ee:ff",
        "model": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "default_options": {
                "blink": True,
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
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "import_confirm"
    assert result["description_placeholders"]["id"] == "aabbccddeeff"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # confirm user is prompted to enter host
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": "1.1.1.1", "port": 1234}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "model": "Konnected Alarm Panel Pro",
        "id": "aabbccddeeff",
        "host": "1.1.1.1",
        "port": 1234,
    }

    # final confirmation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"


async def test_import_ssdp_host_user_finish(hass, mock_panel):
    """Test importing a pro panel with no host info which ssdp discovers."""
    mock_panel.get_status.return_value = {
        "chipId": "somechipid",
        "mac": "11:22:33:44:55:66",
        "model": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "default_options": {
                "blink": True,
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
            "id": "somechipid",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "import_confirm"
    assert result["description_placeholders"]["id"] == "somechipid"

    # discover the panel via ssdp
    ssdp_result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "ssdp_location": "http://0.0.0.0:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL_PRO,
        },
    )
    assert ssdp_result["type"] == "abort"
    assert ssdp_result["reason"] == "already_in_progress"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "model": "Konnected Alarm Panel Pro",
        "id": "somechipid",
        "host": "0.0.0.0",
        "port": 1234,
    }

    # final confirmation
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"


async def test_ssdp_already_configured(hass, mock_panel):
    """Test if a discovered panel has already been configured."""
    MockConfigEntry(
        domain="konnected",
        data={"host": "0.0.0.0", "port": 1234},
        unique_id="112233445566",
    ).add_to_hass(hass)
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "model": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "ssdp_location": "http://0.0.0.0:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL_PRO,
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_ssdp_host_update(hass, mock_panel):
    """Test if a discovered panel has already been configured but changed host."""
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
                "3": "Digital Sensor",
                "7": "Digital Sensor",
                "11": "Binary Sensor",
                "4": "Switchable Output",
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
                {"zone": "3", "type": "dht"},
                {"zone": "7", "type": "ds18b20", "name": "temper"},
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

    MockConfigEntry(
        domain="konnected",
        data=device_config,
        options=device_options,
        unique_id="112233445566",
    ).add_to_hass(hass)
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "model": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "ssdp_location": "http://1.1.1.1:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL_PRO,
        },
    )
    assert result["type"] == "abort"

    # confirm the host value was updated, access_token was not
    entry = hass.config_entries.async_entries(config_flow.DOMAIN)[0]
    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["port"] == 1234
    assert entry.data["access_token"] == "11223344556677889900"


async def test_import_existing_config(hass, mock_panel):
    """Test importing a host with an existing config file."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "model": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=konnected.DEVICE_SCHEMA_YAML(
            {
                "host": "1.2.3.4",
                "port": 1234,
                "id": "112233445566",
                "binary_sensors": [
                    {"zone": "2", "type": "door"},
                    {"zone": 6, "type": "window", "name": "winder", "inverse": True},
                    {"zone": "10", "type": "door"},
                    {"zone": "11", "type": "window"},
                ],
                "sensors": [
                    {"zone": "3", "type": "dht"},
                    {"zone": 7, "type": "ds18b20", "name": "temper"},
                ],
                "switches": [
                    {"zone": "4"},
                    {
                        "zone": 8,
                        "name": "switcher",
                        "activation": "low",
                        "momentary": 50,
                        "pause": 100,
                        "repeat": 4,
                    },
                    {
                        "zone": 8,
                        "name": "alarm",
                        "activation": "low",
                        "momentary": 100,
                        "pause": 100,
                        "repeat": -1,
                    },
                    {"zone": "out1"},
                    {"zone": "alarm1"},
                ],
            }
        ),
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "host": "1.2.3.4",
        "port": 1234,
        "id": "112233445566",
        "model": "Konnected Pro",
        "access_token": result["data"]["access_token"],
        "default_options": {
            "io": {
                "1": "Disabled",
                "5": "Disabled",
                "9": "Disabled",
                "12": "Disabled",
                "out": "Disabled",
                "alarm2_out2": "Disabled",
                "2": "Binary Sensor",
                "6": "Binary Sensor",
                "10": "Binary Sensor",
                "3": "Digital Sensor",
                "7": "Digital Sensor",
                "11": "Binary Sensor",
                "4": "Switchable Output",
                "8": "Switchable Output",
                "out1": "Switchable Output",
                "alarm1": "Switchable Output",
            },
            "blink": True,
            "api_host": "",
            "discovery": True,
            "binary_sensors": [
                {"zone": "2", "type": "door", "inverse": False},
                {"zone": "6", "type": "window", "name": "winder", "inverse": True},
                {"zone": "10", "type": "door", "inverse": False},
                {"zone": "11", "type": "window", "inverse": False},
            ],
            "sensors": [
                {"zone": "3", "type": "dht", "poll_interval": 3},
                {"zone": "7", "type": "ds18b20", "name": "temper", "poll_interval": 3},
            ],
            "switches": [
                {"activation": "high", "zone": "4"},
                {
                    "zone": "8",
                    "name": "switcher",
                    "activation": "low",
                    "momentary": 50,
                    "pause": 100,
                    "repeat": 4,
                },
                {
                    "zone": "8",
                    "name": "alarm",
                    "activation": "low",
                    "momentary": 100,
                    "pause": 100,
                    "repeat": -1,
                },
                {"activation": "high", "zone": "out1"},
                {"activation": "high", "zone": "alarm1"},
            ],
        },
    }


async def test_import_existing_config_entry(hass, mock_panel):
    """Test importing a host that has an existing config entry."""
    MockConfigEntry(
        domain="konnected",
        data={
            "host": "0.0.0.0",
            "port": 1111,
            "access_token": "ORIGINALTOKEN",
            "id": "112233445566",
            "extra": "something",
        },
        unique_id="112233445566",
    ).add_to_hass(hass)

    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "model": "Konnected Pro",
    }

    # utilize a global access token this time
    hass.data[config_flow.DOMAIN] = {"access_token": "SUPERSECRETTOKEN"}
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "default_options": {
                "blink": True,
                "discovery": True,
                "io": {
                    "1": "Disabled",
                    "10": "Binary Sensor",
                    "11": "Disabled",
                    "12": "Disabled",
                    "2": "Binary Sensor",
                    "3": "Disabled",
                    "4": "Disabled",
                    "5": "Disabled",
                    "6": "Binary Sensor",
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
                    {"inverse": True, "type": "Window", "name": "winder", "zone": "6"},
                    {"inverse": False, "type": "door", "zone": "10"},
                ],
            },
        },
    )

    assert result["type"] == "abort"

    # We should have updated the host info but not the access token
    assert len(hass.config_entries.async_entries("konnected")) == 1
    assert hass.config_entries.async_entries("konnected")[0].data == {
        "host": "1.2.3.4",
        "port": 1234,
        "access_token": "ORIGINALTOKEN",
        "id": "112233445566",
        "model": "Konnected Pro",
        "extra": "something",
    }


async def test_import_pin_config(hass, mock_panel):
    """Test importing a host with an existing config file that specifies pin configs."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "model": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=konnected.DEVICE_SCHEMA_YAML(
            {
                "host": "1.2.3.4",
                "port": 1234,
                "id": "112233445566",
                "binary_sensors": [
                    {"pin": 1, "type": "door"},
                    {"pin": "2", "type": "window", "name": "winder", "inverse": True},
                    {"zone": "3", "type": "door"},
                ],
                "sensors": [
                    {"zone": 4, "type": "dht"},
                    {"pin": "7", "type": "ds18b20", "name": "temper"},
                ],
                "switches": [
                    {
                        "pin": "8",
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
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "host": "1.2.3.4",
        "port": 1234,
        "id": "112233445566",
        "model": "Konnected Pro",
        "access_token": result["data"]["access_token"],
        "default_options": {
            "io": {
                "7": "Disabled",
                "8": "Disabled",
                "9": "Disabled",
                "10": "Disabled",
                "11": "Disabled",
                "12": "Disabled",
                "out1": "Disabled",
                "alarm1": "Disabled",
                "alarm2_out2": "Disabled",
                "1": "Binary Sensor",
                "2": "Binary Sensor",
                "3": "Binary Sensor",
                "4": "Digital Sensor",
                "5": "Digital Sensor",
                "6": "Switchable Output",
                "out": "Switchable Output",
            },
            "blink": True,
            "api_host": "",
            "discovery": True,
            "binary_sensors": [
                {"zone": "1", "type": "door", "inverse": False},
                {"zone": "2", "type": "window", "name": "winder", "inverse": True},
                {"zone": "3", "type": "door", "inverse": False},
            ],
            "sensors": [
                {"zone": "4", "type": "dht", "poll_interval": 3},
                {"zone": "5", "type": "ds18b20", "name": "temper", "poll_interval": 3},
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
                {"activation": "high", "zone": "6"},
            ],
        },
    }


async def test_option_flow(hass, mock_panel):
    """Test config flow options."""
    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected",
            "access_token": "11223344556677889900",
            "default_options": config_flow.OPTIONS_SCHEMA({config_flow.CONF_IO: {}}),
        }
    )

    device_options = config_flow.OPTIONS_SCHEMA({"io": {}})

    entry = MockConfigEntry(
        domain="konnected",
        data=device_config,
        options=device_options,
        unique_id="112233445566",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_io"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "1": "Disabled",
            "2": "Binary Sensor",
            "3": "Digital Sensor",
            "4": "Switchable Output",
            "5": "Disabled",
            "6": "Binary Sensor",
            "out": "Switchable Output",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"
    assert result["description_placeholders"] == {
        "zone": "Zone 2",
    }

    # zone 2
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "door"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"
    assert result["description_placeholders"] == {
        "zone": "Zone 6",
    }

    # zone 6
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"type": "window", "name": "winder", "inverse": True},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"
    assert result["description_placeholders"] == {
        "zone": "Zone 3",
    }

    # zone 3
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "dht"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"
    assert result["description_placeholders"] == {
        "zone": "Zone 4",
        "state": "1",
    }

    # zone 4
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"
    assert result["description_placeholders"] == {
        "zone": "OUT",
        "state": "1",
    }

    # zone out
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "switcher",
            "activation": "low",
            "momentary": 50,
            "pause": 100,
            "repeat": 4,
            "more_states": "Yes",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"
    assert result["description_placeholders"] == {
        "zone": "OUT",
        "state": "2",
    }

    # zone out - state 2
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "alarm",
            "activation": "low",
            "momentary": 100,
            "pause": 100,
            "repeat": -1,
            "more_states": "No",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "options_misc"
    # make sure we enforce url format
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "discovery": False,
            "blink": True,
            "override_api_host": True,
            "api_host": "badhosturl",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "options_misc"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "discovery": False,
            "blink": True,
            "override_api_host": True,
            "api_host": "http://overridehost:1111",
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "io": {
            "2": "Binary Sensor",
            "3": "Digital Sensor",
            "4": "Switchable Output",
            "6": "Binary Sensor",
            "out": "Switchable Output",
        },
        "discovery": False,
        "blink": True,
        "api_host": "http://overridehost:1111",
        "binary_sensors": [
            {"zone": "2", "type": "door", "inverse": False},
            {"zone": "6", "type": "window", "name": "winder", "inverse": True},
        ],
        "sensors": [{"zone": "3", "type": "dht", "poll_interval": 3}],
        "switches": [
            {"activation": "high", "zone": "4"},
            {
                "zone": "out",
                "name": "switcher",
                "activation": "low",
                "momentary": 50,
                "pause": 100,
                "repeat": 4,
            },
            {
                "zone": "out",
                "name": "alarm",
                "activation": "low",
                "momentary": 100,
                "pause": 100,
                "repeat": -1,
            },
        ],
    }


async def test_option_flow_pro(hass, mock_panel):
    """Test config flow options for pro board."""
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

    device_options = config_flow.OPTIONS_SCHEMA({"io": {}})

    entry = MockConfigEntry(
        domain="konnected",
        data=device_config,
        options=device_options,
        unique_id="112233445566",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_io"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "1": "Disabled",
            "2": "Binary Sensor",
            "3": "Digital Sensor",
            "4": "Switchable Output",
            "5": "Disabled",
            "6": "Binary Sensor",
            "7": "Digital Sensor",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_io_ext"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "8": "Switchable Output",
            "9": "Disabled",
            "10": "Binary Sensor",
            "11": "Binary Sensor",
            "12": "Disabled",
            "out1": "Switchable Output",
            "alarm1": "Switchable Output",
            "alarm2_out2": "Disabled",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 2
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "door"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 6
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"type": "window", "name": "winder", "inverse": True},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 10
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "door"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 11
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "window"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 3
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "dht"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 7
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "ds18b20", "name": "temper"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 4
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 8
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "name": "switcher",
            "activation": "low",
            "momentary": 50,
            "pause": 100,
            "repeat": 4,
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone out1
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone alarm1
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_misc"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"discovery": False, "blink": True, "override_api_host": False},
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {
        "io": {
            "10": "Binary Sensor",
            "11": "Binary Sensor",
            "2": "Binary Sensor",
            "3": "Digital Sensor",
            "4": "Switchable Output",
            "6": "Binary Sensor",
            "7": "Digital Sensor",
            "8": "Switchable Output",
            "alarm1": "Switchable Output",
            "out1": "Switchable Output",
        },
        "discovery": False,
        "blink": True,
        "api_host": "",
        "binary_sensors": [
            {"zone": "2", "type": "door", "inverse": False},
            {"zone": "6", "type": "window", "name": "winder", "inverse": True},
            {"zone": "10", "type": "door", "inverse": False},
            {"zone": "11", "type": "window", "inverse": False},
        ],
        "sensors": [
            {"zone": "3", "type": "dht", "poll_interval": 3},
            {"zone": "7", "type": "ds18b20", "name": "temper", "poll_interval": 3},
        ],
        "switches": [
            {"activation": "high", "zone": "4"},
            {
                "zone": "8",
                "name": "switcher",
                "activation": "low",
                "momentary": 50,
                "pause": 100,
                "repeat": 4,
            },
            {"activation": "high", "zone": "out1"},
            {"activation": "high", "zone": "alarm1"},
        ],
    }


async def test_option_flow_import(hass, mock_panel):
    """Test config flow options imported from configuration.yaml."""
    device_options = config_flow.OPTIONS_SCHEMA(
        {
            "io": {
                "1": "Binary Sensor",
                "2": "Digital Sensor",
                "3": "Switchable Output",
            },
            "binary_sensors": [
                {"zone": "1", "type": "window", "name": "winder", "inverse": True},
            ],
            "sensors": [{"zone": "2", "type": "ds18b20", "name": "temper"}],
            "switches": [
                {
                    "zone": "3",
                    "name": "switcher",
                    "activation": "low",
                    "momentary": 50,
                    "pause": 100,
                    "repeat": 4,
                },
                {
                    "zone": "3",
                    "name": "alarm",
                    "activation": "low",
                    "momentary": 100,
                    "pause": 100,
                    "repeat": -1,
                },
            ],
        }
    )

    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "11223344556677889900",
            "default_options": device_options,
        }
    )

    entry = MockConfigEntry(
        domain="konnected", data=device_config, unique_id="112233445566"
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_io"

    # confirm the defaults are set based on current config - we"ll spot check this throughout
    schema = result["data_schema"]({})
    assert schema["1"] == "Binary Sensor"
    assert schema["2"] == "Digital Sensor"
    assert schema["3"] == "Switchable Output"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "1": "Binary Sensor",
            "2": "Digital Sensor",
            "3": "Switchable Output",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_io_ext"
    schema = result["data_schema"]({})
    assert schema["8"] == "Disabled"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 1
    schema = result["data_schema"]({})
    assert schema["type"] == "window"
    assert schema["name"] == "winder"
    assert schema["inverse"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"type": "door"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 2
    schema = result["data_schema"]({})
    assert schema["type"] == "ds18b20"
    assert schema["name"] == "temper"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"type": "dht"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 3
    schema = result["data_schema"]({})
    assert schema["name"] == "switcher"
    assert schema["activation"] == "low"
    assert schema["momentary"] == 50
    assert schema["pause"] == 100
    assert schema["repeat"] == 4
    assert schema["more_states"] == "Yes"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"activation": "high", "more_states": "No"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_misc"

    schema = result["data_schema"]({})
    assert schema["blink"] is True
    assert schema["discovery"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"discovery": True, "blink": False, "override_api_host": False},
    )

    # verify the updated fields
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "io": {"1": "Binary Sensor", "2": "Digital Sensor", "3": "Switchable Output"},
        "discovery": True,
        "blink": False,
        "api_host": "",
        "binary_sensors": [
            {"zone": "1", "type": "door", "inverse": True, "name": "winder"},
        ],
        "sensors": [
            {"zone": "2", "type": "dht", "poll_interval": 3, "name": "temper"},
        ],
        "switches": [
            {
                "zone": "3",
                "name": "switcher",
                "activation": "high",
                "momentary": 50,
                "pause": 100,
                "repeat": 4,
            },
        ],
    }


async def test_option_flow_existing(hass, mock_panel):
    """Test config flow options with existing already in place."""
    device_options = config_flow.OPTIONS_SCHEMA(
        {
            "io": {
                "1": "Binary Sensor",
                "2": "Digital Sensor",
                "3": "Switchable Output",
            },
            "binary_sensors": [
                {"zone": "1", "type": "window", "name": "winder", "inverse": True},
            ],
            "sensors": [{"zone": "2", "type": "ds18b20", "name": "temper"}],
            "switches": [
                {
                    "zone": "3",
                    "name": "switcher",
                    "activation": "low",
                    "momentary": 50,
                    "pause": 100,
                    "repeat": 4,
                },
            ],
        }
    )

    device_config = config_flow.CONFIG_ENTRY_SCHEMA(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "model": "Konnected Pro",
            "access_token": "11223344556677889900",
            "default_options": config_flow.OPTIONS_SCHEMA({"io": {}}),
        }
    )

    entry = MockConfigEntry(
        domain="konnected",
        data=device_config,
        options=device_options,
        unique_id="112233445566",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_io"

    # confirm the defaults are pulled in from the existing options
    schema = result["data_schema"]({})
    assert schema["1"] == "Binary Sensor"
    assert schema["2"] == "Digital Sensor"
    assert schema["3"] == "Switchable Output"
