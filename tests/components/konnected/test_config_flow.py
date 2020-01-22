"""Tests for Konnected Alarm Panel config flow."""
from asynctest import patch
import pytest

from homeassistant.components.konnected import config_flow
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP

from tests.common import MockConfigEntry


# pylint: disable=redefined-outer-name
@pytest.fixture
async def mock_panel():
    """Mock a Konnected Panel bridge."""
    with patch("konnected.Client", autospec=True) as konn_client:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            konn_client.host = host
            konn_client.port = port
            return konn_client

        konn_client.side_effect = mock_constructor
        mock_panel.ClientError = config_flow.CannotConnect
        yield konn_client


async def test_flow_works(hass, mock_panel):
    """Test config flow ."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"port": 1234, "host": "1.2.3.4"}
    )

    assert mock_panel.host == "1.2.3.4"
    assert mock_panel.port == "1234"
    assert len(mock_panel.get_status.mock_calls) == 1

    assert result["type"] == "form"
    assert result["step_id"] == "io"

    result = await hass.config_entries.flow.async_configure(
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

    # zone 2
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"type": "door"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 6
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"type": "window", "name": "winder", "inverse": True},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 3
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"type": "dht"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 4
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone out
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "switcher",
            "activation": "low",
            "momentary": 50,
            "pause": 100,
            "repeat": 4,
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "host": "1.2.3.4",
        "port": 1234,
        "id": "112233445566",
        "blink": True,
        "discovery": True,
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
        ],
    }


async def test_pro_flow_works(hass, mock_panel):
    """Test config flow ."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"port": 1234, "host": "1.2.3.4"}
    )

    assert mock_panel.host == "1.2.3.4"
    assert mock_panel.port == "1234"
    assert len(mock_panel.get_status.mock_calls) == 1

    assert result["type"] == "form"
    assert result["step_id"] == "io"

    result = await hass.config_entries.flow.async_configure(
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
    assert result["step_id"] == "io_ext"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "8": "Switchable Output",
            "9": "Disabled",
            "10": "Binary Sensor",
            "11": "Digital Sensor",
            "12": "Disabled",
            "out1": "Switchable Output",
            "alarm1": "Switchable Output",
            "alarm2_out2": "Disabled",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 2
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"type": "door"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 6
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"type": "window", "name": "winder", "inverse": True},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 10
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"type": "door"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 3
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"type": "dht"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 7
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"type": "ds18b20", "name": "temper"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 11
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"type": "dht"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 4
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 8
    result = await hass.config_entries.flow.async_configure(
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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone alarm1
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        "host": "1.2.3.4",
        "port": 1234,
        "id": "112233445566",
        "blink": True,
        "discovery": True,
        "binary_sensors": [
            {"zone": "2", "type": "door", "inverse": False},
            {"zone": "6", "type": "window", "name": "winder", "inverse": True},
            {"zone": "10", "type": "door", "inverse": False},
        ],
        "sensors": [
            {"zone": "3", "type": "dht", "poll_interval": 3},
            {"zone": "7", "type": "ds18b20", "name": "temper", "poll_interval": 3},
            {"zone": "11", "type": "dht", "poll_interval": 3},
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


async def test_ssdp(hass, mock_panel):
    """Test a panel being discovered."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "ssdp"},
        data={
            "ssdp_location": "http://1.2.3.4:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "io"
    assert result["description_placeholders"]["model"] == "Konnected Alarm Panel"

    # ensure the discovered info is saved
    # pylint: disable=protected-access
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert flow.device_id == "112233445566"
    assert flow.model == config_flow.KONN_MODEL
    assert flow.host == "1.2.3.4"
    assert flow.port == "1234"

    flow = next(
        (
            flow
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
    )
    assert flow["context"]["device_id"] == "112233445566"


async def test_ssdp_pro(hass, mock_panel):
    """Test a Pro panel being discovered."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "ssdp"},
        data={
            "ssdp_location": "http://1.2.3.4:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL_PRO,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "io"
    assert result["description_placeholders"]["model"] == "Konnected Alarm Panel Pro"

    # ensure the discovered info is saved
    # pylint: disable=protected-access
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert flow.device_id == "112233445566"
    assert flow.model == config_flow.KONN_MODEL_PRO
    assert flow.host == "1.2.3.4"
    assert flow.port == "1234"


async def test_import_cannot_connect(hass, mock_panel):
    """Test importing a host that we cannot connect to."""
    mock_panel.get_status.side_effect = config_flow.CannotConnect
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "import"},
        data={"host": "0.0.0.0", "port": 1234, "id": "112233445566"},
    )

    # Create the entry even if panel isn't available - we'll update the host once we know it
    assert result["type"] == "create_entry"


async def test_import_no_host_user_finish(hass, mock_panel):
    """Test importing a panel with no host info."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "import"}, data={"id": "112233445566"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # wait for user to enter host info to finish
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": "1.1.1.1", "port": 1234}
    )

    assert result["type"] == "create_entry"


async def test_import_no_host_ssdp_finish(hass, mock_panel):
    """Test importing a panel with no host info."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={"id": "112233445566"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # second flow started by ssdp should hijack the first
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            "ssdp_location": "http://1.2.3.4:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL_PRO,
        },
    )
    assert result["type"] == "create_entry"


async def test_ssdp_already_configured(hass):
    """Test if a discovered panel has already been configured."""
    MockConfigEntry(domain="konnected", data={"host": "0.0.0.0"}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "ssdp"},
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
                {"zone": "11", "type": "dht"},
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
    MockConfigEntry(domain="konnected", data=device_config).add_to_hass(hass)
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "ssdp"},
        data={
            "ssdp_location": "http://1.1.1.1:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL_PRO,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"]["host"] == "1.1.1.1"
    assert result["data"]["port"] == 1234
    assert result["data"]["id"] == "112233445566"
    assert result["data"]["binary_sensors"][0] == {
        "inverse": False,
        "type": "door",
        "zone": "2",
    }


async def test_import_existing_config(hass, mock_panel):
    """Test importing a host with an existing config file."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "import"},
        data={
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "binary_sensors": [
                {"zone": "2", "type": "door"},
                {"zone": 6, "type": "window", "name": "winder", "inverse": True},
                {"zone": "10", "type": "door"},
            ],
            "sensors": [
                {"zone": "3", "type": "dht"},
                {"zone": 7, "type": "ds18b20", "name": "temper"},
                {"zone": "11", "type": "dht"},
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
                {"zone": "out1"},
                {"zone": "alarm1"},
            ],
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {
        "host": "1.2.3.4",
        "port": 1234,
        "id": "112233445566",
        "blink": True,
        "discovery": True,
        "binary_sensors": [
            {"zone": "2", "type": "door", "inverse": False},
            {"zone": "6", "type": "window", "name": "winder", "inverse": True},
            {"zone": "10", "type": "door", "inverse": False},
        ],
        "sensors": [
            {"zone": "3", "type": "dht", "poll_interval": 3},
            {"zone": "7", "type": "ds18b20", "name": "temper", "poll_interval": 3},
            {"zone": "11", "type": "dht", "poll_interval": 3},
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


async def test_import_existing_config_entry(hass, mock_panel):
    """Test importing a host that has an existing config entry."""
    MockConfigEntry(
        domain="konnected", data={"host": "0.0.0.0", "id": "112233445566"}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="konnected", data={"host": "1.2.3.4", "id": "aabbccddeeff"}
    ).add_to_hass(hass)
    assert len(hass.config_entries.async_entries("konnected")) == 2

    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "import"},
        data={
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "binary_sensors": [
                {"zone": "2", "type": "door"},
                {"zone": "6", "type": "window", "name": "winder", "inverse": True},
                {"zone": "10", "type": "door"},
            ],
        },
    )

    assert result["type"] == "create_entry"

    # We should have replaced the two old entries with an updated one.
    assert len(hass.config_entries.async_entries("konnected")) == 1
    hass.config_entries.async_entries("konnected")[0].data["id"] = "112233445566"
    hass.config_entries.async_entries("konnected")[0].data["host"] = "1.2.3.4"


async def test_import_pin_config(hass, mock_panel):
    """Test importing a host with an existing config file that specifies pin configs."""
    mock_panel.get_status.return_value = {
        "mac": "11:22:33:44:55:66",
        "name": "Konnected Pro",
    }

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": "import"},
        data={
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
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {
        "host": "1.2.3.4",
        "port": 1234,
        "id": "112233445566",
        "blink": True,
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
    }
