"""Test the raw log stream of the system log."""

import logging
import logging.handlers
from pathlib import Path
from queue import SimpleQueue
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import system_log
from homeassistant.components.system_log.const import RAW_UPDATE_COOLDOWN
from homeassistant.components.system_log.stream import (
    DATA_RAW_LOG_STREAM,
    WEBSOCKET_CONNECTION_LOGGER,
)
from homeassistant.const import KEY_DATA_LOGGING
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.logging import HomeAssistantQueueHandler

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator

_LOGGER = logging.getLogger("test_logger")


async def test_subscribe_raw(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    tmp_path: Path,
) -> None:
    """Test the raw log starts with the end of the log file and streams new lines."""
    log_file = tmp_path / "home-assistant.log"
    # Long lines, so only the end of the file is read
    log_file.write_text("".join(f"line {i:<1000}\n" for i in range(150)))
    hass.data[KEY_DATA_LOGGING] = str(log_file)
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "system_log/subscribe_raw"})
    msg = await client.receive_json()
    assert msg["success"]

    msg = await client.receive_json()
    assert msg["event"] == [f"line {i:<1000}" for i in range(50, 150)]

    _LOGGER.warning("First message")
    await hass.async_block_till_done()
    msg = await client.receive_json()
    assert len(msg["event"]) == 1
    assert "WARNING" in msg["event"][0]
    assert "[test_logger] First message" in msg["event"][0]

    # Sent after the cooldown, websocket debug logging is not streamed
    _LOGGER.warning("Second message")
    logging.getLogger(WEBSOCKET_CONNECTION_LOGGER).debug("Sending message")
    _LOGGER.warning("Third message")
    await hass.async_block_till_done()
    await client.send_json_auto_id({"type": "ping"})
    msg = await client.receive_json()
    assert msg["type"] == "pong"

    freezer.tick(RAW_UPDATE_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    msg = await client.receive_json()
    lines = [line for line in msg["event"] if "test_logger" in line]
    assert len(lines) == 2
    assert "Second message" in lines[0]
    assert "Third message" in lines[1]
    assert not [line for line in msg["event"] if WEBSOCKET_CONNECTION_LOGGER in line]


@pytest.mark.parametrize(
    "log_file",
    [pytest.param(None, id="no_log_file"), pytest.param("/missing.log", id="missing")],
)
@pytest.mark.parametrize(
    "integration",
    [pytest.param({}, id="all"), pytest.param({"integration": "demo"}, id="demo")],
)
async def test_subscribe_raw_without_log_file(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    log_file: str | None,
    integration: dict[str, str],
) -> None:
    """Test the raw log starts empty without a readable log file."""
    hass.data[KEY_DATA_LOGGING] = log_file
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "system_log/subscribe_raw", **integration})
    msg = await client.receive_json()
    assert msg["success"]
    msg = await client.receive_json()
    assert msg["event"] == []


async def test_unsubscribe_raw(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the handler is only attached while there are subscribers."""
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()
    handler = hass.data[DATA_RAW_LOG_STREAM]
    assert handler not in logging.root.handlers

    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "system_log/subscribe_raw"})
    msg = await client.receive_json()
    assert msg["success"]
    subscription = msg["id"]
    await client.receive_json()
    assert handler in logging.root.handlers

    await client.send_json_auto_id(
        {"type": "unsubscribe_events", "subscription": subscription}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert handler not in logging.root.handlers


async def test_subscribe_raw_integration(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an integration only gets its own lines, starting with the log file."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.demo")
    log_file = tmp_path / "home-assistant.log"
    log_file.write_text(
        "2026-10-10 08:58:11.594 INFO (MainThread) [homeassistant.setup] Setup\n"
        "2026-10-10 08:58:12.001 ERROR (MainThread) [homeassistant.components.demo]"
        " Failed\n"
        "Traceback (most recent call last):\n"
        "ValueError: boom\n"
        "2026-10-10 08:58:12.002 DEBUG (Thread-3 (worker)) [homeassistant.components"
        ".demo.sensor] Polled\n"
        "2026-10-10 08:58:12.003 INFO (MainThread) [homeassistant.components"
        ".demo_other] Not demo\n"
        "Continued not demo\n"
    )
    hass.data[KEY_DATA_LOGGING] = str(log_file)
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {"type": "system_log/subscribe_raw", "integration": "demo"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    msg = await client.receive_json()
    assert msg["event"] == [
        "2026-10-10 08:58:12.001 ERROR (MainThread) [homeassistant.components.demo]"
        " Failed",
        "Traceback (most recent call last):",
        "ValueError: boom",
        "2026-10-10 08:58:12.002 DEBUG (Thread-3 (worker)) [homeassistant.components"
        ".demo.sensor] Polled",
    ]

    _LOGGER.warning("Other message")
    logging.getLogger("homeassistant.components.demo.sensor").debug("Demo message")
    logging.getLogger("homeassistant.components.demo_other").warning("Not demo")
    await hass.async_block_till_done()

    msg = await client.receive_json()
    assert len(msg["event"]) == 1
    assert "[homeassistant.components.demo.sensor] Demo message" in msg["event"][0]


async def test_subscribe_raw_lines_logged_while_reading(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test lines logged while reading the log file are sent once."""
    hass.data[KEY_DATA_LOGGING] = str(tmp_path / "home-assistant.log")
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()
    handler = hass.data[DATA_RAW_LOG_STREAM]

    def _read_log_tail(path: str, lines: int) -> list[str]:
        # Already written to the log file when it is read
        _LOGGER.warning("In the file")
        in_file = handler.format(caplog.records[-1])
        _LOGGER.warning("Not in the file yet")
        return ["Older line", in_file]

    client = await hass_ws_client()
    with patch(
        "homeassistant.components.system_log.stream._read_log_tail",
        _read_log_tail,
    ):
        await client.send_json_auto_id({"type": "system_log/subscribe_raw"})
        msg = await client.receive_json()
    assert msg["success"]

    msg = await client.receive_json()
    assert len(msg["event"]) == 3
    assert msg["event"][0] == "Older line"
    assert "In the file" in msg["event"][1]
    assert "Not in the file yet" in msg["event"][2]


async def test_subscribe_raw_unknown_integration(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test subscribing to an unknown integration fails."""
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {"type": "system_log/subscribe_raw", "integration": "does_not_exist"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


async def test_subscribe_raw_console_formatter(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the stream uses the formatter of the console log."""
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("console: %(message)s"))
    queue_handler = HomeAssistantQueueHandler(SimpleQueue())
    queue_handler.listener = logging.handlers.QueueListener(SimpleQueue(), console)
    logging.root.addHandler(queue_handler)
    try:
        client = await hass_ws_client()
        await client.send_json_auto_id({"type": "system_log/subscribe_raw"})
        msg = await client.receive_json()
        assert msg["success"]
        await client.receive_json()

        _LOGGER.warning("Colored message")
        await hass.async_block_till_done()
        msg = await client.receive_json()
    finally:
        logging.root.removeHandler(queue_handler)
    assert msg["event"] == ["console: Colored message"]


async def test_subscribe_raw_all_and_integration(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test subscribers for all lines and for one integration at the same time."""
    await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    demo_client = await hass_ws_client()
    await demo_client.send_json_auto_id(
        {"type": "system_log/subscribe_raw", "integration": "demo"}
    )
    assert (await demo_client.receive_json())["success"]
    await demo_client.receive_json()

    all_client = await hass_ws_client()
    await all_client.send_json_auto_id({"type": "system_log/subscribe_raw"})
    assert (await all_client.receive_json())["success"]
    await all_client.receive_json()

    freezer.tick(RAW_UPDATE_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    _LOGGER.warning("Other message")
    logging.getLogger("homeassistant.components.demo").warning("Demo message")
    await hass.async_block_till_done()

    msg = await all_client.receive_json()
    assert any("Other message" in line for line in msg["event"])
    assert any("Demo message" in line for line in msg["event"])
    msg = await demo_client.receive_json()
    assert len(msg["event"]) == 1
    assert "Demo message" in msg["event"][0]
