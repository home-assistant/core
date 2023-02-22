"""Common functions for RFLink component tests and generic platform tests."""

from unittest.mock import Mock

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.rflink import (
    CONF_KEEPALIVE_IDLE,
    CONF_RECONNECT_INTERVAL,
    DATA_ENTITY_LOOKUP,
    DEFAULT_TCP_KEEPALIVE_IDLE_TIMER,
    DOMAIN as RFLINK_DOMAIN,
    EVENT_KEY_COMMAND,
    EVENT_KEY_SENSOR,
    SERVICE_SEND_COMMAND,
    TMP_ENTITY,
    RflinkCommand,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    SERVICE_STOP_COVER,
    SERVICE_TURN_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


async def mock_rflink(
    hass, config, domain, monkeypatch, failures=None, failcommand=False
):
    """Create mock RFLink asyncio protocol, test component setup."""
    transport, protocol = (Mock(), Mock())

    async def send_command_ack(*command):
        return not failcommand

    protocol.send_command_ack = Mock(wraps=send_command_ack)

    def send_command(*command):
        return not failcommand

    protocol.send_command = Mock(wraps=send_command)

    async def create_rflink_connection(*args, **kwargs):
        """Return mocked transport and protocol."""
        # failures can be a list of booleans indicating in which sequence
        # creating a connection should success or fail
        if failures:
            fail = failures.pop()
        else:
            fail = False

        if fail:
            raise ConnectionRefusedError
        else:
            return transport, protocol

    mock_create = Mock(wraps=create_rflink_connection)
    monkeypatch.setattr(
        "homeassistant.components.rflink.create_rflink_connection", mock_create
    )

    await async_setup_component(hass, "rflink", config)
    await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    # hook into mock config for injecting events
    event_callback = mock_create.call_args_list[0][1]["event_callback"]
    assert event_callback

    disconnect_callback = mock_create.call_args_list[0][1]["disconnect_callback"]

    return event_callback, mock_create, protocol, disconnect_callback


async def test_version_banner(hass: HomeAssistant, monkeypatch) -> None:
    """Test sending unknown commands doesn't cause issues."""
    # use sensor domain during testing main platform
    domain = "sensor"
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        domain: {
            "platform": "rflink",
            "devices": {"test": {"name": "test", "sensor_type": "temperature"}},
        },
    }

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, domain, monkeypatch)

    event_callback(
        {
            "hardware": "Nodo RadioFrequencyLink",
            "firmware": "RFLink Gateway",
            "version": "1.1",
            "revision": "45",
        }
    )


async def test_send_no_wait(hass: HomeAssistant, monkeypatch) -> None:
    """Test command sending without ack."""
    domain = "switch"
    config = {
        "rflink": {"port": "/dev/ttyABC0", "wait_for_ack": False},
        domain: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {"name": "test", "aliases": ["test_alias_0_0"]}
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, domain, monkeypatch)

    await hass.services.async_call(
        domain, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.test"}
    )
    await hass.async_block_till_done()
    assert protocol.send_command.call_args_list[0][0][0] == "protocol_0_0"
    assert protocol.send_command.call_args_list[0][0][1] == "off"


async def test_cover_send_no_wait(hass: HomeAssistant, monkeypatch) -> None:
    """Test command sending to a cover device without ack."""
    domain = "cover"
    config = {
        "rflink": {"port": "/dev/ttyABC0", "wait_for_ack": False},
        domain: {
            "platform": "rflink",
            "devices": {
                "RTS_0100F2_0": {"name": "test", "aliases": ["test_alias_0_0"]}
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, domain, monkeypatch)

    await hass.services.async_call(
        domain, SERVICE_STOP_COVER, {ATTR_ENTITY_ID: "cover.test"}
    )
    await hass.async_block_till_done()
    assert protocol.send_command.call_args_list[0][0][0] == "RTS_0100F2_0"
    assert protocol.send_command.call_args_list[0][0][1] == "STOP"


async def test_send_command(hass: HomeAssistant, monkeypatch) -> None:
    """Test send_command service."""
    domain = "rflink"
    config = {"rflink": {"port": "/dev/ttyABC0"}}

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, domain, monkeypatch)

    await hass.services.async_call(
        domain,
        SERVICE_SEND_COMMAND,
        {"device_id": "newkaku_0000c6c2_1", "command": "on"},
    )
    await hass.async_block_till_done()
    assert protocol.send_command_ack.call_args_list[0][0][0] == "newkaku_0000c6c2_1"
    assert protocol.send_command_ack.call_args_list[0][0][1] == "on"


async def test_send_command_invalid_arguments(hass: HomeAssistant, monkeypatch) -> None:
    """Test send_command service."""
    domain = "rflink"
    config = {"rflink": {"port": "/dev/ttyABC0"}}

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, domain, monkeypatch)

    # one argument missing
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(domain, SERVICE_SEND_COMMAND, {"command": "on"})

    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            domain, SERVICE_SEND_COMMAND, {"device_id": "newkaku_0000c6c2_1"}
        )

    # no arguments
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(domain, SERVICE_SEND_COMMAND, {})

    await hass.async_block_till_done()
    assert protocol.send_command_ack.call_args_list == []

    # bad command (no_command)
    success = await hass.services.async_call(
        domain,
        SERVICE_SEND_COMMAND,
        {"device_id": "newkaku_0000c6c2_1", "command": "no_command"},
    )
    assert not success, "send command should not succeed for unknown command"


async def test_send_command_event_propagation(hass: HomeAssistant, monkeypatch) -> None:
    """Test event propagation for send_command service."""
    domain = "light"
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        domain: {
            "platform": "rflink",
            "devices": {
                "protocol_0_1": {"name": "test1"},
            },
        },
    }

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(hass, config, domain, monkeypatch)

    # default value = 'off'
    assert hass.states.get(f"{domain}.test1").state == "off"

    await hass.services.async_call(
        "rflink",
        SERVICE_SEND_COMMAND,
        {"device_id": "protocol_0_1", "command": "on"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert protocol.send_command_ack.call_args_list[0][0][0] == "protocol_0_1"
    assert protocol.send_command_ack.call_args_list[0][0][1] == "on"
    assert hass.states.get(f"{domain}.test1").state == "on"

    await hass.services.async_call(
        "rflink",
        SERVICE_SEND_COMMAND,
        {"device_id": "protocol_0_1", "command": "alloff"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert protocol.send_command_ack.call_args_list[1][0][0] == "protocol_0_1"
    assert protocol.send_command_ack.call_args_list[1][0][1] == "alloff"
    assert hass.states.get(f"{domain}.test1").state == "off"


async def test_reconnecting_after_disconnect(hass: HomeAssistant, monkeypatch) -> None:
    """An unexpected disconnect should cause a reconnect."""
    domain = "sensor"
    config = {
        "rflink": {"port": "/dev/ttyABC0", CONF_RECONNECT_INTERVAL: 0},
        domain: {"platform": "rflink"},
    }

    # setup mocking rflink module
    _, mock_create, _, disconnect_callback = await mock_rflink(
        hass, config, domain, monkeypatch
    )

    assert disconnect_callback, "disconnect callback not passed to rflink"

    # rflink initiated disconnect
    disconnect_callback(None)

    await hass.async_block_till_done()

    # we expect 2 call, the initial and reconnect
    assert mock_create.call_count == 2


async def test_reconnecting_after_failure(hass: HomeAssistant, monkeypatch) -> None:
    """A failure to reconnect should be retried."""
    domain = "sensor"
    config = {
        "rflink": {"port": "/dev/ttyABC0", CONF_RECONNECT_INTERVAL: 0},
        domain: {"platform": "rflink"},
    }

    # success first time but fail second
    failures = [False, True, False]

    # setup mocking rflink module
    _, mock_create, _, disconnect_callback = await mock_rflink(
        hass, config, domain, monkeypatch, failures=failures
    )

    # rflink initiated disconnect
    disconnect_callback(None)

    # wait for reconnects to have happened
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # we expect 3 calls, the initial and 2 reconnects
    assert mock_create.call_count == 3


async def test_error_when_not_connected(hass: HomeAssistant, monkeypatch) -> None:
    """Sending command should error when not connected."""
    domain = "switch"
    config = {
        "rflink": {"port": "/dev/ttyABC0", CONF_RECONNECT_INTERVAL: 0},
        domain: {
            "platform": "rflink",
            "devices": {
                "protocol_0_0": {"name": "test", "aliases": ["test_alias_0_0"]}
            },
        },
    }

    # success first time but fail second
    failures = [False, True, False]

    # setup mocking rflink module
    _, _, _, disconnect_callback = await mock_rflink(
        hass, config, domain, monkeypatch, failures=failures
    )

    # rflink initiated disconnect
    disconnect_callback(None)

    success = await hass.services.async_call(
        domain, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.test"}
    )
    assert not success, "changing state should not succeed when disconnected"


async def test_async_send_command_error(hass: HomeAssistant, monkeypatch) -> None:
    """Sending command should error when protocol fails."""
    domain = "rflink"
    config = {"rflink": {"port": "/dev/ttyABC0"}}

    # setup mocking rflink module
    _, _, protocol, _ = await mock_rflink(
        hass, config, domain, monkeypatch, failcommand=True
    )

    success = await hass.services.async_call(
        domain,
        SERVICE_SEND_COMMAND,
        {"device_id": "newkaku_0000c6c2_1", "command": SERVICE_TURN_OFF},
    )
    await hass.async_block_till_done()
    assert not success, "send command should not succeed if failcommand=True"
    assert protocol.send_command_ack.call_args_list[0][0][0] == "newkaku_0000c6c2_1"
    assert protocol.send_command_ack.call_args_list[0][0][1] == SERVICE_TURN_OFF


async def test_race_condition(hass: HomeAssistant, monkeypatch) -> None:
    """Test race condition for unknown components."""
    domain = "light"
    config = {"rflink": {"port": "/dev/ttyABC0"}, domain: {"platform": "rflink"}}
    tmp_entity = TMP_ENTITY.format("test3")

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, domain, monkeypatch)

    # test event for new unconfigured sensor
    event_callback({"id": "test3", "command": "off"})
    event_callback({"id": "test3", "command": "on"})

    # tmp_entity added to EVENT_KEY_COMMAND
    assert tmp_entity in hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_COMMAND]["test3"]
    # tmp_entity must no be added to EVENT_KEY_SENSOR
    assert tmp_entity not in hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_SENSOR]["test3"]

    await hass.async_block_till_done()

    # test  state of new sensor
    new_sensor = hass.states.get(f"{domain}.test3")
    assert new_sensor
    assert new_sensor.state == "off"

    event_callback({"id": "test3", "command": "on"})
    await hass.async_block_till_done()
    # tmp_entity must be deleted from EVENT_KEY_COMMAND
    assert tmp_entity not in hass.data[DATA_ENTITY_LOOKUP][EVENT_KEY_COMMAND]["test3"]

    # test  state of new sensor
    new_sensor = hass.states.get(f"{domain}.test3")
    assert new_sensor
    assert new_sensor.state == "on"


async def test_not_connected(hass: HomeAssistant, monkeypatch) -> None:
    """Test Error when sending commands to a disconnected device."""
    test_device = RflinkCommand("DUMMY_DEVICE")
    RflinkCommand.set_rflink_protocol(None)
    with pytest.raises(HomeAssistantError):
        await test_device._async_handle_command("turn_on")


async def test_keepalive(
    hass: HomeAssistant, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Validate negative keepalive values."""
    keepalive_value = -3
    domain = RFLINK_DOMAIN
    config = {
        RFLINK_DOMAIN: {
            CONF_HOST: "10.10.0.1",
            CONF_PORT: 1234,
            CONF_KEEPALIVE_IDLE: keepalive_value,
        }
    }

    # setup mocking rflink module
    _, mock_create, _, _ = await mock_rflink(hass, config, domain, monkeypatch)

    assert mock_create.call_args_list[0][1]["host"] == "10.10.0.1"
    assert mock_create.call_args_list[0][1]["port"] == 1234
    assert (
        mock_create.call_args_list[0][1]["keepalive"] is None
    )  # negative keepalive is not allowed
    assert (
        f"A bogus TCP Keepalive IDLE timer was provided ({keepalive_value} secs)"
        in caplog.text
    )


async def test2_keepalive(hass, monkeypatch, caplog):
    """Validate very short keepalive values."""
    keepalive_value = 30
    domain = RFLINK_DOMAIN
    config = {
        RFLINK_DOMAIN: {
            CONF_HOST: "10.10.0.1",
            CONF_PORT: 1234,
            CONF_KEEPALIVE_IDLE: keepalive_value,
        }
    }

    # setup mocking rflink module
    _, mock_create, _, _ = await mock_rflink(hass, config, domain, monkeypatch)

    assert mock_create.call_args_list[0][1]["host"] == "10.10.0.1"
    assert mock_create.call_args_list[0][1]["port"] == 1234
    assert (
        mock_create.call_args_list[0][1]["keepalive"] == keepalive_value
    )  # very short keepalive is allowed but warned
    assert (
        f"A very short TCP Keepalive IDLE timer was provided ({keepalive_value} secs)"
        in caplog.text
    )


async def test3_keepalive(hass, monkeypatch, caplog):
    """Validate keepalive=0 value."""
    domain = RFLINK_DOMAIN
    config = {
        RFLINK_DOMAIN: {CONF_HOST: "10.10.0.1", CONF_PORT: 1234, CONF_KEEPALIVE_IDLE: 0}
    }

    # setup mocking rflink module
    _, mock_create, _, _ = await mock_rflink(hass, config, domain, monkeypatch)

    assert mock_create.call_args_list[0][1]["host"] == "10.10.0.1"
    assert mock_create.call_args_list[0][1]["port"] == 1234
    assert (
        mock_create.call_args_list[0][1]["keepalive"] is None
    )  # keepalive=0 will disable it
    assert "TCP Keepalive IDLE timer was provided" not in caplog.text


async def test_default_keepalive(
    hass: HomeAssistant, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Validate keepalive=0 value."""
    domain = RFLINK_DOMAIN
    config = {RFLINK_DOMAIN: {CONF_HOST: "10.10.0.1", CONF_PORT: 1234}}

    # setup mocking rflink module
    _, mock_create, _, _ = await mock_rflink(hass, config, domain, monkeypatch)

    assert mock_create.call_args_list[0][1]["host"] == "10.10.0.1"
    assert mock_create.call_args_list[0][1]["port"] == 1234
    assert (
        mock_create.call_args_list[0][1]["keepalive"]
        == DEFAULT_TCP_KEEPALIVE_IDLE_TIMER
    )  # no keepalive config will default it
    assert "TCP Keepalive IDLE timer was provided" not in caplog.text


async def test_unique_id(hass: HomeAssistant, monkeypatch) -> None:
    """Validate the device unique_id."""

    DOMAIN = "sensor"
    config = {
        "rflink": {"port": "/dev/ttyABC0"},
        DOMAIN: {
            "platform": "rflink",
            "devices": {
                "my_humidity_device_unique_id": {
                    "name": "humidity_device",
                    "sensor_type": "humidity",
                    "aliases": ["test_alias_02_0"],
                },
                "my_temperature_device_unique_id": {
                    "name": "temperature_device",
                    "sensor_type": "temperature",
                    "aliases": ["test_alias_02_0"],
                },
            },
        },
    }

    registry = er.async_get(hass)

    # setup mocking rflink module
    event_callback, _, _, _ = await mock_rflink(hass, config, DOMAIN, monkeypatch)

    humidity_entry = registry.async_get("sensor.humidity_device")
    assert humidity_entry
    assert humidity_entry.unique_id == "my_humidity_device_unique_id"

    temperature_entry = registry.async_get("sensor.temperature_device")
    assert temperature_entry
    assert temperature_entry.unique_id == "my_temperature_device_unique_id"
