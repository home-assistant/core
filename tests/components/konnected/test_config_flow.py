"""Tests for Konnected Alarm Panel config flow."""
from unittest.mock import patch

from homeassistant.components.konnected import config_flow
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP

from tests.common import MockConfigEntry, mock_coro


async def test_flow_works(hass, aioclient_mock):
    """Test config flow ."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.return_value = mock_coro(
            {"mac": "11:22:33:44:55:66", "name": "Konnected"}
        )

        result = await flow.async_step_user({"port": 1234, "host": "1.2.3.4"})

    assert mock_panel.host == "1.2.3.4"
    assert mock_panel.port == "1234"
    assert len(mock_panel.get_status.mock_calls) == 1

    assert result["type"] == "form"
    assert result["step_id"] == "io"

    result = await flow.async_step_io(
        {
            "1": "Disabled",
            "2": "Binary Sensor",
            "3": "Digital Sensor",
            "4": "Switchable Output",
            "5": "Disabled",
            "6": "Binary Sensor",
            "out": "Switchable Output",
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 2
    result = await flow.async_step_options_binary({"type": "door"})
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 6
    result = await flow.async_step_options_binary(
        {"type": "window", "name": "winder", "inverse": True}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 3
    result = await flow.async_step_options_digital({"type": "dht"})
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 4
    result = await flow.async_step_options_switch({})
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone out
    result = await flow.async_step_options_switch(
        {
            "name": "switcher",
            "activation": "low",
            "momentary": 50,
            "pause": 100,
            "repeat": 4,
        }
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


async def test_pro_flow_works(hass, aioclient_mock):
    """Test config flow ."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.return_value = mock_coro(
            {"mac": "11:22:33:44:55:66", "name": "Konnected Pro"}
        )

        result = await flow.async_step_user({"port": 1234, "host": "1.2.3.4"})

    assert mock_panel.host == "1.2.3.4"
    assert mock_panel.port == "1234"
    assert len(mock_panel.get_status.mock_calls) == 1

    assert result["type"] == "form"
    assert result["step_id"] == "io"

    result = await flow.async_step_io(
        {
            "1": "Disabled",
            "2": "Binary Sensor",
            "3": "Digital Sensor",
            "4": "Switchable Output",
            "5": "Disabled",
            "6": "Binary Sensor",
            "7": "Digital Sensor",
            "8": "Switchable Output",
            "9": "Disabled",
            "10": "Binary Sensor",
            "11": "Digital Sensor",
            "12": "Disabled",
            "out1": "Switchable Output",
            "alarm1": "Switchable Output",
            "alarm2_out2": "Disabled",
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "io_ext"
    result = await flow.async_step_io_ext(
        {
            "8": "Switchable Output",
            "9": "Disabled",
            "10": "Binary Sensor",
            "11": "Digital Sensor",
            "12": "Disabled",
            "out1": "Switchable Output",
            "alarm1": "Switchable Output",
            "alarm2_out2": "Disabled",
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 2
    result = await flow.async_step_options_binary({"type": "door"})
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 6
    result = await flow.async_step_options_binary(
        {"type": "window", "name": "winder", "inverse": True}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_binary"

    # zone 10
    result = await flow.async_step_options_binary({"type": "door"})
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 3
    result = await flow.async_step_options_digital({"type": "dht"})
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 7
    result = await flow.async_step_options_digital(
        {"type": "ds18b20", "name": "temper"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_digital"

    # zone 11
    result = await flow.async_step_options_digital({"type": "dht"})
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 4
    result = await flow.async_step_options_switch({})
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone 8
    result = await flow.async_step_options_switch(
        {
            "name": "switcher",
            "activation": "low",
            "momentary": 50,
            "pause": 100,
            "repeat": 4,
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone out1
    result = await flow.async_step_options_switch({})
    assert result["type"] == "form"
    assert result["step_id"] == "options_switch"

    # zone alarm1
    result = await flow.async_step_options_switch({})
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


async def test_ssdp(hass):
    """Test a panel being discovered."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.return_value = mock_coro(
            {"mac": "11:22:33:44:55:66", "name": "Konnected"}
        )

        result = await flow.async_step_ssdp(
            {
                "ssdp_location": "http://1.2.3.4:1234/Device.xml",
                "manufacturer": config_flow.KONN_MANUFACTURER,
                "modelName": config_flow.KONN_MODEL,
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "io"
    assert result["description_placeholders"]["model"] == "Konnected Alarm Panel"
    assert flow.device_id == "112233445566"
    assert flow.model == config_flow.KONN_MODEL
    assert flow.host == "1.2.3.4"
    assert flow.port == "1234"


async def test_ssdp_pro(hass):
    """Test a Pro panel being discovered."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.return_value = mock_coro(
            {"mac": "11:22:33:44:55:66", "name": "Konnected Pro"}
        )

        result = await flow.async_step_ssdp(
            {
                "ssdp_location": "http://1.2.3.4:1234/Device.xml",
                "manufacturer": config_flow.KONN_MANUFACTURER,
                "modelName": config_flow.KONN_MODEL_PRO,
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "io"
    assert result["description_placeholders"]["model"] == "Konnected Alarm Panel Pro"
    assert flow.device_id == "112233445566"
    assert flow.model == config_flow.KONN_MODEL_PRO
    assert flow.host == "1.2.3.4"
    assert flow.port == "1234"


async def test_import_cannot_connect(hass):
    """Test importing a host that we cannot connect to."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.side_effect = config_flow.CannotConnect
        mock_panel.ClientError = config_flow.CannotConnect

        result = await flow.async_step_import(
            {"host": "0.0.0.0", "port": 1234, "id": "112233445566"}
        )

    # Create the entry even if panel isn't available - we'll update the host once we know it
    assert result["type"] == "create_entry"


async def test_import_no_host_user_finish(hass):
    """Test importing a panel with no host info."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.return_value = mock_coro(
            {"mac": "11:22:33:44:55:66", "name": "Konnected Pro"}
        )

        result = await flow.async_step_import({"id": "112233445566"})
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        # wait for user to enter host info to finish
        result = await flow.async_step_user({"host": "1.1.1.1", "port": 1234})

        assert result["type"] == "create_entry"


async def test_import_no_host_ssdp_finish(hass):
    """Test importing a panel with no host info."""
    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.return_value = mock_coro(
            {"mac": "11:22:33:44:55:66", "name": "Konnected Pro"}
        )

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

    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_ssdp(
        {
            "ssdp_location": "http://0.0.0.0:1234/Device.xml",
            "manufacturer": config_flow.KONN_MANUFACTURER,
            "modelName": config_flow.KONN_MODEL_PRO,
        }
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_ssdp_host_update(hass):
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
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch("konnected.Client") as mock_panel:

        def mock_constructor(host, port, websession):
            """Fake the panel constructor."""
            mock_panel.host = host
            mock_panel.port = port
            return mock_panel

        mock_panel.side_effect = mock_constructor
        mock_panel.get_status.return_value = mock_coro(
            {"mac": "11:22:33:44:55:66", "name": "Konnected Pro"}
        )

        result = await flow.async_step_ssdp(
            {
                "ssdp_location": "http://1.1.1.1:1234/Device.xml",
                "manufacturer": config_flow.KONN_MANUFACTURER,
                "modelName": config_flow.KONN_MODEL_PRO,
            }
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


async def test_import_existing_config(hass):
    """Test importing a host with an existing config file."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_import(
        {
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
        }
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


async def test_import_existing_config_entry(hass):
    """Test importing a host that has an existing config entry."""
    MockConfigEntry(
        domain="konnected", data={"host": "0.0.0.0", "id": "112233445566"}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="konnected", data={"host": "1.2.3.4", "id": "aabbccddeeff"}
    ).add_to_hass(hass)
    assert len(hass.config_entries.async_entries("konnected")) == 2

    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_import(
        {
            "host": "1.2.3.4",
            "port": 1234,
            "id": "112233445566",
            "binary_sensors": [
                {"zone": "2", "type": "door"},
                {"zone": "6", "type": "window", "name": "winder", "inverse": True},
                {"zone": "10", "type": "door"},
            ],
        }
    )

    assert result["type"] == "create_entry"

    # We did not process the result of this entry but already removed the old
    # ones. So we should have 0 entries.
    assert len(hass.config_entries.async_entries("konnected")) == 0


async def test_import_pin_config(hass):
    """Test importing a host with an existing config file that specifies pin configs."""
    flow = config_flow.KonnectedFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_import(
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
