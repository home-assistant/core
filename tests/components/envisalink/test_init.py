"""Tests for the Envisalink setup."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.envisalink import (
    LoginTimeout,
    async_connect_panel,
    disconnect_panel,
)
from homeassistant.components.envisalink.const import (
    CONF_EVL_PORT,
    CONF_EVL_VERSION,
    CONF_PANEL_TYPE,
    CONF_PASS,
    CONF_USERNAME,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import (
    ALARM_ENTITY,
    DOMAIN,
    KEYPAD_ENTITY,
    MOCK_CODE,
    MOCK_DATA,
    MOCK_OPTIONS,
    MOCK_YAML_CONFIG,
    ZONE_ENTITY,
    setup_envisalink,
    setup_envisalink_yaml,
)

from tests.common import MockConfigEntry


async def test_setup_creates_entities(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup creates the alarm, keypad and zone entities."""
    assert await setup_envisalink(hass)

    assert hass.states.get(ALARM_ENTITY) is not None
    assert hass.states.get(KEYPAD_ENTITY) is not None
    assert hass.states.get(ZONE_ENTITY) is not None


async def test_setup_fails_on_login_failure(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup returns False when the Envisalink rejects the login."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_failure(
        None
    )

    assert await setup_envisalink(hass) is False
    assert hass.states.get(ALARM_ENTITY) is None


async def test_setup_retries_on_login_timeout(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup schedules a retry when our outer login timeout fires.

    Regression test: the outer asyncio.timeout in async_connect_panel fully
    disconnects the panel before giving up (unlike pyenvisalink's own
    tolerate-and-retry timeout), so setup must raise ConfigEntryNotReady
    instead of proceeding with a dead controller.
    """
    mock_controller.start.side_effect = None  # never resolves the connection

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS)
    with (
        patch("homeassistant.components.envisalink.LOGIN_RESPONSE_TIMEOUT", 0),
        patch("homeassistant.components.envisalink.DEFAULT_TIMEOUT", 0),
    ):
        assert await setup_envisalink(hass, entry) is False

    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_controller.stop.assert_called_once()


async def test_setup_succeeds_on_connection_timeout(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test setup proceeds (retry mode) when the first connection times out."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_timeout(
        None
    )

    assert await setup_envisalink(hass)
    assert hass.states.get(ALARM_ENTITY) is not None


async def test_controller_stopped_on_shutdown(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the controller connection is stopped on Home Assistant shutdown."""
    assert await setup_envisalink(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_controller.stop.assert_called_once()


async def test_invoke_custom_function_service(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the PGM service forwards the code, partition and function."""
    assert await setup_envisalink(hass)

    # Distinct pgm/partition values so the assertion pins each positional arg
    # of command_output(code, partition, custom_function).
    await hass.services.async_call(
        DOMAIN,
        "invoke_custom_function",
        {"pgm": "7", "partition": "2"},
        blocking=True,
    )

    mock_controller.command_output.assert_called_once_with(MOCK_CODE, "2", "7")


async def test_invoke_custom_function_service_no_loaded_entry(
    hass: HomeAssistant,
) -> None:
    """Test the PGM service errors when no entry is set up."""
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError, match="currently set up"):
        await hass.services.async_call(
            DOMAIN,
            "invoke_custom_function",
            {"pgm": "7", "partition": "2"},
            blocking=True,
        )


async def test_import_yaml_config(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML config is imported with entities and a repair issue."""
    assert await setup_envisalink_yaml(hass)

    assert hass.states.get(ALARM_ENTITY) is not None
    assert hass.states.get(KEYPAD_ENTITY) is not None
    assert hass.states.get(ZONE_ENTITY) is not None
    assert issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}")


async def test_async_connect_panel_stops_controller_on_cancel(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test cancelling a pending connection still stops the controller.

    Regression test: if the caller (e.g. an aborted config flow) is
    cancelled before the login result resolves, pyenvisalink's background
    reconnect/keepalive loops must still be stopped, or they run forever on
    an orphaned, unreferenced panel instance.
    """
    mock_controller.start.side_effect = None  # never resolves the connection

    task = hass.async_create_task(
        async_connect_panel(
            hass,
            MOCK_DATA[CONF_HOST],
            MOCK_DATA[CONF_EVL_PORT],
            MOCK_DATA[CONF_PANEL_TYPE],
            MOCK_DATA[CONF_EVL_VERSION],
            MOCK_DATA[CONF_USERNAME],
            MOCK_DATA[CONF_PASS],
        )
    )
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    mock_controller.stop.assert_called_once()


async def test_async_connect_panel_times_out_without_login_response(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test a connection that never gets a login response doesn't hang forever.

    Regression test: if the wrong panel_type is selected, the panel's replies
    are never recognized as a login success/failure/timeout, so none of the
    login callbacks fire. Without an outer bound, this leaves the connection
    attempt (and anything awaiting it, e.g. the config flow) hung forever.

    This must be distinguishable from the library's own tolerate-and-retry
    timeout: disconnect_panel() has already fully torn down the connection
    here, so the caller can't treat it as still-running and self-healing.
    """
    mock_controller.start.side_effect = None  # never resolves the connection

    with (
        patch("homeassistant.components.envisalink.LOGIN_RESPONSE_TIMEOUT", 0),
        pytest.raises(LoginTimeout),
    ):
        await async_connect_panel(
            hass,
            MOCK_DATA[CONF_HOST],
            MOCK_DATA[CONF_EVL_PORT],
            MOCK_DATA[CONF_PANEL_TYPE],
            MOCK_DATA[CONF_EVL_VERSION],
            MOCK_DATA[CONF_USERNAME],
            MOCK_DATA[CONF_PASS],
            connection_timeout=0,
        )

    mock_controller.stop.assert_called_once()


async def test_async_connect_panel_disconnects_on_start_error(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test a controller that fails to start is still disconnected.

    Regression test: start() used to run outside the try/except guarding
    disconnect_panel(), so an error raised directly from start() (as opposed
    to one reported later through a login callback) bypassed cleanup
    entirely and leaked the controller.
    """
    mock_controller.start.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await async_connect_panel(
            hass,
            MOCK_DATA[CONF_HOST],
            MOCK_DATA[CONF_EVL_PORT],
            MOCK_DATA[CONF_PANEL_TYPE],
            MOCK_DATA[CONF_EVL_VERSION],
            MOCK_DATA[CONF_USERNAME],
            MOCK_DATA[CONF_PASS],
        )

    mock_controller.stop.assert_called_once()


def test_disconnect_panel_cancels_pending_reconnect() -> None:
    """Test disconnect_panel force-closes the transport and cancels reconnects.

    Regression test: pyenvisalink's own stop() doesn't close the transport
    or cancel an already-scheduled reconnect when given an external event
    loop (always true for us) - a reconnect scheduled before stop() is
    called fires anyway, since reconnect() doesn't check the shutdown flag
    itself. mock_controller is autospec'd and doesn't know about the
    library's private _client/_reconnect_task attributes, so this uses a
    plain mock to verify the real interaction.
    """
    controller = MagicMock()
    controller._client._reconnect_task = MagicMock()

    disconnect_panel(controller)

    controller.stop.assert_called_once()
    controller._client.disconnect.assert_called_once()
    controller._client._reconnect_task.cancel.assert_called_once()


def test_disconnect_panel_without_pending_reconnect() -> None:
    """Test disconnect_panel doesn't error when no reconnect is scheduled."""
    controller = MagicMock()
    controller._client._reconnect_task = None

    disconnect_panel(controller)

    controller.stop.assert_called_once()
    controller._client.disconnect.assert_called_once()


async def test_setup_entry_disconnects_panel_on_later_failure(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test the panel is disconnected if setup fails after connecting.

    Regression test: a failure between connecting and finishing setup (e.g.
    async_forward_entry_setups() itself raising) must still disconnect the
    panel. Home Assistant's core failure handling only unregisters the
    on_unload callbacks on a failed setup - it does not call
    async_unload_entry - so without its own cleanup, async_setup_entry would
    leave the panel connected and its background reconnect running,
    unreferenced, forever.

    Note this does NOT cover a platform crashing while creating an entity
    (e.g. for an out-of-range zone/partition number): Home Assistant's own
    entity_platform setup swallows exceptions raised by a platform's
    async_setup_entry before they ever reach us, so that failure mode can't
    reach this cleanup path at all - confirmed by forcing
    binary_sensor.async_setup_entry to raise directly through the real
    hass.config_entries.async_setup() call, which still reports success.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS)
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("boom"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR

    mock_controller.stop.assert_called_once()


async def test_import_yaml_config_cannot_connect(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a YAML import failure raises the integration-specific repair issue."""
    mock_controller.start.side_effect = lambda: mock_controller.callback_login_failure(
        None
    )

    assert await setup_envisalink_yaml(hass)

    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_auth"
    )


async def test_import_yaml_config_invalid_zone_number(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an out-of-range YAML zone number raises the integration issue."""
    config = {
        DOMAIN: {
            **MOCK_YAML_CONFIG[DOMAIN],
            "zones": {65: {"name": "Out of Range", "type": "door"}},
        }
    }

    assert await setup_envisalink_yaml(hass, config)

    issue = issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_invalid_zone_number"
    )
    assert issue is not None
    assert issue.translation_placeholders["number"] == "65"
    assert issue.translation_placeholders["max"] == "64"
