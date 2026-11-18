"""Test Hikvision integration setup and unload."""

from datetime import timedelta
import logging
import threading
from unittest.mock import MagicMock, patch
from xml.etree.ElementTree import ParseError

from freezegun.api import FrozenDateTimeFactory
from pyhik.isapi import (
    ISAPIAuthError,
    ISAPIConnectionError,
    ISAPIError,
    ISAPINotSupportedError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import requests

from homeassistant.components.hikvision import (
    EVENT_PLATFORMS,
    IMAGE_SETTINGS_RETRY_INTERVAL,
    PLATFORMS,
    STREAM_CREDENTIALS_ID,
)
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.components.hikvision.coordinator import SCAN_INTERVAL
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from . import setup_integration
from .conftest import TEST_DEVICE_ID, TEST_HOST, TEST_PASSWORD, TEST_PORT, TEST_USERNAME


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test successful setup and unload of config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.return_value.start_stream.assert_called_once()

    # Verify HikCamera was called with the verify_ssl parameter
    mock_hikcamera.assert_called_once_with(
        f"http://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_stream_stopped_on_shutdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the event stream thread is joined before the event loop closes."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_stream_stopped_when_shutdown_starts_during_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the stream is stopped when shutdown begins while setting up."""
    hass.set_state(CoreState.stopping)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_setup_entry_with_ssl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup with ssl enabled passes ssl parameter to HikCamera."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_SSL: True}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify HikCamera was called over HTTPS, verifying the certificate
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


@pytest.mark.parametrize(
    ("entry_data", "expected_verify_ssl"),
    [
        ({CONF_VERIFY_SSL: False}, False),
        ({CONF_VERIFY_SSL: True}, True),
        # Entries created before the option existed keep verifying
        (None, True),
    ],
    ids=["unverified", "verified", "legacy_entry"],
)
async def test_setup_entry_ssl_verification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entry_data: dict[str, bool] | None,
    expected_verify_ssl: bool,
) -> None:
    """Test the certificate verification choice is passed to HikCamera."""
    data = {**mock_config_entry.data, CONF_SSL: True}
    data.pop(CONF_VERIFY_SSL)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**data, **(entry_data or {})}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}",
        TEST_PORT,
        TEST_USERNAME,
        TEST_PASSWORD,
        expected_verify_ssl,
    )


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup fails on connection error."""
    mock_hikcamera.side_effect = requests.exceptions.RequestException(
        "Connection failed"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup fails when device_id is None."""
    mock_hikcamera.return_value.get_id = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("amount_of_channels", [2])
@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_setup_entry_nvr_channels_ssl_verification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    mock_hik_get_channels: MagicMock,
    verify_ssl: bool,
) -> None:
    """Test the certificate verification choice is used to list NVR channels."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SSL: True, CONF_VERIFY_SSL: verify_ssl},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_get_channels.assert_called_once_with(
        TEST_HOST, TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True, verify_ssl
    )


async def test_setup_entry_nvr_fetches_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup fetches NVR events for NVR devices."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_called_once()


async def test_setup_entry_nvr_skips_videoloss(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test NVR event injection skips videoloss (watchdog event)."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "VMD": [1, 2],
        "videoloss": [1, 2, 3],
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_called_once_with({"Motion": [1, 2]})


async def test_setup_entry_nvr_skips_unmapped_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test NVR event injection skips events not in SENSOR_MAP."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "VMD": [1],
        "audioexception": [1, 2],
    }

    with caplog.at_level(logging.DEBUG):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_called_once_with({"Motion": [1]})
    assert "Skipping unmapped event type: audioexception" in caplog.text


async def test_setup_entry_nvr_skips_all_unknown_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test NVR event injection with only unknown events does not inject."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "videoloss": [1],
        "audioexception": [2],
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_not_called()


async def test_setup_entry_nvr_event_fetch_request_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup continues when NVR event fetch fails with request error."""
    mock_hik_nvr.return_value.get_event_triggers.side_effect = (
        requests.exceptions.RequestException("Connection error")
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()
    assert f"Unable to fetch event triggers from {TEST_HOST}" in caplog.text


async def test_setup_entry_nvr_event_fetch_parse_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup continues when NVR event fetch fails with parse error."""
    mock_hik_nvr.return_value.get_event_triggers.side_effect = ParseError("Invalid XML")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()
    assert f"Unable to fetch event triggers from {TEST_HOST}" in caplog.text


async def test_setup_entry_nvr_no_events_returned(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup continues when NVR returns no events."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()


async def test_setup_entry_nvr_empty_events_returned(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup continues when NVR returns empty events."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {}

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()


async def test_setup_with_rejected_credentials_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a rejected password asks for new credentials instead of retrying."""
    mock_hikcamera.return_value.get_id = None
    mock_hikcamera.return_value.auth_failed = True

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
    # Core also raises a repair for the entry, linking to the reauth flow.
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN,
        f"config_entry_reauth_{DOMAIN}_{mock_config_entry.entry_id}",
    )


async def test_setup_unreachable_device_is_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a device that gives no ID, without rejecting the login, is retried."""
    mock_hikcamera.return_value.get_id = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_nvr_without_image_settings_still_loads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_isapi_client: MagicMock,
) -> None:
    """Test that an NVR whose cameras have no image settings loads as before."""
    mock_hikcamera.return_value.get_type = "NVR"

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_isapi_client.return_value.get_image_channels.assert_called_once_with(
        proxy=True
    )
    mock_isapi_client.return_value.get_image_settings.assert_not_called()
    mock_isapi_client.return_value.close.assert_called_once()


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("ssl", "verify_ssl"), [(False, True), (True, True), (True, False)]
)
async def test_image_settings_client_uses_the_entry_settings(
    hass: HomeAssistant,
    mock_isapi_client: MagicMock,
    ssl: bool,
    verify_ssl: bool,
) -> None:
    """Test that the image settings client connects like the camera does."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: 8080,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: ssl,
            CONF_VERIFY_SSL: verify_ssl,
        },
        unique_id=TEST_DEVICE_ID,
    )

    await setup_integration(hass, entry)

    mock_isapi_client.assert_called_once_with(
        TEST_HOST, 8080, TEST_USERNAME, TEST_PASSWORD, ssl, verify_ssl
    )


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("error", "warnings"),
    [
        pytest.param(ISAPINotSupportedError("not supported"), [], id="not_supported"),
        pytest.param(
            ISAPIAuthError("Insufficient permissions"),
            [
                f"Not allowed to read the image settings of {TEST_HOST}: Insufficient permissions"
            ],
            id="not_allowed",
        ),
        pytest.param(
            ISAPIError("Request failed with status 500"),
            [
                f"Unable to read the image settings of {TEST_HOST}: Request failed with status 500"
            ],
            id="error",
        ),
    ],
)
async def test_camera_without_readable_image_settings_still_loads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    error: ISAPIError,
    warnings: list[str],
) -> None:
    """Test that failing to read image settings never stops the camera loading."""
    mock_isapi_client.return_value.get_image_settings.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.image_coordinators
    mock_isapi_client.return_value.close.assert_called_once()
    assert [
        record.getMessage()
        for record in caplog.records
        if record.name == "homeassistant.components.hikvision"
        and record.levelno == logging.WARNING
    ] == warnings


@pytest.mark.usefixtures("mock_hikcamera")
async def test_unreadable_image_values_do_not_stop_the_camera_loading(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a failing first read of the values never stops the camera loading."""
    mock_image_settings.get_image_values.side_effect = ISAPIError("timeout")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.close.assert_called_once()
    assert "Unable to read the image values" in caplog.text
    assert hass.states.async_entity_ids("binary_sensor")


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize("failing", ["get_image_settings", "get_image_values"])
async def test_image_settings_are_tried_again_after_a_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    failing: str,
) -> None:
    """Test a camera that was busy gets its image entities without a manual reload."""
    getattr(mock_image_settings, failing).side_effect = ISAPIConnectionError("timeout")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.image_coordinators == []

    getattr(mock_image_settings, failing).side_effect = None
    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.image_coordinators


@pytest.mark.usefixtures("mock_hikcamera")
async def test_recorder_listing_is_tried_again_after_a_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a recorder that reports itself as a camera is read again after a timeout."""
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = ISAPINotSupportedError("Not found", 404)
    client.get_image_channels.side_effect = ISAPIConnectionError("timeout")
    await setup_integration(hass, mock_config_entry)
    assert client.get_image_channels.call_count == 1

    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.get_image_channels.call_count == 2


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize("status", [500, 503])
async def test_image_settings_are_tried_again_after_a_server_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    status: int,
) -> None:
    """Test a camera that answered busy gets its image entities when it recovers."""
    mock_image_settings.get_image_settings.side_effect = ISAPIError("busy", status)

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.image_coordinators == []

    mock_image_settings.get_image_settings.side_effect = None
    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.image_coordinators


@pytest.mark.usefixtures("mock_hikcamera")
async def test_image_settings_are_not_retried_after_an_unexpected_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a camera that answers with an error is not reloaded again and again."""
    mock_isapi_client.return_value.get_image_settings.side_effect = ISAPIError("bad")
    await setup_integration(hass, mock_config_entry)
    mock_isapi_client.reset_mock()

    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_isapi_client.assert_not_called()


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    "error",
    [
        ISAPIAuthError("Forbidden", 403),
        ISAPINotSupportedError("Not found", 404),
    ],
)
async def test_image_values_are_not_retried_when_the_camera_will_not_give_them(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    error: ISAPIError,
) -> None:
    """Test a camera that refuses the values is not reloaded again and again."""
    mock_image_settings.get_image_values.side_effect = error
    await setup_integration(hass, mock_config_entry)
    assert not mock_config_entry.runtime_data.image_coordinators
    mock_image_settings.reset_mock()

    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_image_settings.get_image_values.assert_not_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_hikcamera")
async def test_retry_of_the_image_settings_is_cancelled_on_unload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test that an unloaded entry is not loaded again by the retry."""
    mock_image_settings.get_image_settings.side_effect = ISAPIConnectionError("timeout")
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    mock_image_settings.get_image_settings.side_effect = None
    freezer.tick(IMAGE_SETTINGS_RETRY_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_rejected_password_while_reading_image_values_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a rejected password on the first read of the values asks for new credentials."""
    mock_image_settings.get_image_values.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_image_settings.close.assert_called_once()
    mock_hikcamera.return_value.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_rejected_password_while_discovering_image_settings_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_isapi_client: MagicMock,
) -> None:
    """Test a rejected password on the image settings discovery asks for new credentials."""
    mock_isapi_client.return_value.get_image_settings.side_effect = ISAPIAuthError(
        "Invalid credentials", 401
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_isapi_client.return_value.close.assert_called_once()
    # The stream would otherwise keep retrying the rejected password.
    mock_hikcamera.return_value.disconnect.assert_called()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("mock_hikcamera")
async def test_image_settings_client_closed_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test that the image settings client is closed when the entry unloads."""
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = None
    client.get_image_settings.return_value = []
    client.get_image_values.return_value = {}

    await setup_integration(hass, mock_config_entry)
    client.close.assert_not_called()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    client.close.assert_called_once()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_image_settings_client_closed_when_the_setup_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_isapi_client: MagicMock,
) -> None:
    """Test the client is closed if the setup ends, or is cancelled, after it."""
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = None
    client.get_image_settings.return_value = []
    client.get_image_values.return_value = {}

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        # The event platforms are forwarded first.
        side_effect=[None, RuntimeError],
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    client.close.assert_called_once()


def _credentials_callback(camera: MagicMock):
    """Return what the integration registered to watch the credentials."""
    registered = [
        call.args
        for call in camera.add_update_callback.call_args_list
        if call.args[1] == STREAM_CREDENTIALS_ID
    ]
    assert len(registered) == 1
    return registered[0][0]


async def test_credentials_rejected_by_the_event_stream_start_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a camera without image settings still asks for new credentials."""
    await setup_integration(hass, mock_config_entry)
    assert not hass.config_entries.flow.async_progress()

    # pyHik stops the stream and calls its callbacks, from the stream thread.
    camera = mock_hikcamera.return_value
    camera.stream_auth_failed = True
    await hass.async_add_executor_job(
        _credentials_callback(camera), STREAM_CREDENTIALS_ID
    )
    await hass.async_block_till_done()

    # pyHik only slows the stream down, so it is stopped here.
    camera.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_a_stream_that_is_only_down_does_not_start_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the callback is called for every change of the stream."""
    await setup_integration(hass, mock_config_entry)

    camera = mock_hikcamera.return_value
    camera.stream_connected = False
    await hass.async_add_executor_job(
        _credentials_callback(camera), STREAM_CREDENTIALS_ID
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.flow.async_progress()


async def test_credentials_refused_before_the_watch_started_start_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a refusal that came while the entry was still being set up is not lost."""
    mock_hikcamera.return_value.stream_auth_failed = True

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_credentials_rejected_by_the_event_stream_stop_the_image_settings(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the image settings do not send the rejected password either."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "number.front_camera_brightness"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
    reads = mock_image_settings.get_image_values.call_count

    camera = mock_hikcamera.return_value
    camera.stream_auth_failed = True
    await hass.async_add_executor_job(
        _credentials_callback(camera), STREAM_CREDENTIALS_ID
    )
    await hass.async_block_till_done()
    freezer.tick(SCAN_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert mock_image_settings.get_image_values.call_count == reads
    camera.disconnect.assert_called()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_credentials_rejected_by_the_stream_are_dealt_with_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the callback, which is called for every change, does not repeat itself."""
    await setup_integration(hass, mock_config_entry)

    camera = mock_hikcamera.return_value
    camera.stream_auth_failed = True
    callback = _credentials_callback(camera)
    for _ in range(3):
        await hass.async_add_executor_job(callback, STREAM_CREDENTIALS_ID)
        await hass.async_block_till_done()

    camera.disconnect.assert_called_once()
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_nothing_is_sent_while_the_stream_is_being_stopped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test a write that comes while the stream is stopped does not send the password."""
    await setup_integration(hass, mock_config_entry)
    camera = mock_hikcamera.return_value
    started = threading.Event()
    release = threading.Event()

    def disconnect() -> None:
        started.set()
        release.wait(10)

    # A plain function, so that it runs in a thread and blocks only itself.
    camera.disconnect = disconnect
    camera.stream_auth_failed = True
    await hass.async_add_executor_job(
        _credentials_callback(camera), STREAM_CREDENTIALS_ID
    )
    await hass.async_add_executor_job(started.wait, 10)

    try:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: "number.front_camera_brightness", ATTR_VALUE: 20},
                blocking=True,
            )
    finally:
        release.set()
    await hass.async_block_till_done()

    mock_image_settings.set_image_setting.assert_not_called()


async def test_credentials_watch_is_removed_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test nothing is left registered on a camera that is shut down."""
    await setup_integration(hass, mock_config_entry)
    camera = mock_hikcamera.return_value
    callback = _credentials_callback(camera)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    camera.remove_update_callback.assert_any_call(callback, STREAM_CREDENTIALS_ID)


@pytest.mark.usefixtures("mock_hikcamera")
async def test_the_event_platforms_do_not_wait_for_the_image_settings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the entities of the events exist before the image settings are read."""
    steps: list[tuple[str, set[Platform]]] = []
    forward = hass.config_entries.async_forward_entry_setups
    discover = mock_image_settings.get_image_settings.return_value

    async def _forward(entry: MockConfigEntry, platforms: list[Platform]) -> None:
        steps.append(("forward", set(platforms)))
        await forward(entry, platforms)

    def _read(*args: object, **kwargs: object) -> object:
        steps.append(("read", set()))
        return discover

    mock_image_settings.get_image_settings.side_effect = _read
    with patch.object(hass.config_entries, "async_forward_entry_setups", _forward):
        await setup_integration(hass, mock_config_entry)

    assert steps[:2] == [
        ("forward", {p for p in PLATFORMS if p in EVENT_PLATFORMS}),
        ("read", set()),
    ]
    assert steps[2] == (
        "forward",
        {p for p in PLATFORMS if p not in EVENT_PLATFORMS},
    )
    assert len(steps) == 3


async def test_a_setup_that_fails_while_reading_the_image_settings_leaves_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test nothing the setup started stays behind when it fails after the events.

    A setup that fails does not call async_unload_entry.
    """
    mock_image_settings.get_image_settings.side_effect = RuntimeError("boom")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    # The entities were unloaded: what is left is what Home Assistant shows for
    # an entry that is not loaded, not entities that are still running.
    states = [
        hass.states.get(entity_id)
        for domain in ("binary_sensor", "camera")
        for entity_id in hass.states.async_entity_ids(domain)
    ]
    assert states
    assert all(state.state == STATE_UNAVAILABLE for state in states)
    # The client is closed, and the stream is stopped.
    mock_image_settings.close.assert_called_once()
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_a_setup_that_fails_after_reading_the_image_settings_leaves_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the client and the stream are released when the image platforms fail."""
    forward = hass.config_entries.async_forward_entry_setups
    calls = 0

    async def _forward(entry: MockConfigEntry, platforms: list[Platform]) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("boom")
        await forward(entry, platforms)

    with patch.object(hass.config_entries, "async_forward_entry_setups", _forward):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_image_settings.close.assert_called_once()
    mock_hikcamera.return_value.disconnect.assert_called_once()
