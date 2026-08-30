"""Test the Haus-Bus config flow."""

import asyncio
import threading
from typing import NoReturn
from unittest.mock import MagicMock, patch

from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the user flow creates a config entry once a device is found."""
    # A plain function, not a MagicMock: hass's test-mode executor-job
    # runner special-cases Mock targets and runs them inline instead of on
    # a worker thread. Left as a Mock, the whole search would complete
    # synchronously within async_configure(), so the flow would cascade
    # straight past SHOW_PROGRESS to CREATE_ENTRY before this test could
    # ever observe the progress step - which is not how it behaves for a
    # real, executor-backed search.
    mock_home_server.searchDevices = lambda: None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "wait_for_device"

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Haus-Bus"
    assert result["data"] == {}


async def test_user_flow_search_timeout_then_retry(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the search-timeout step and that submitting it retries the search."""
    mock_home_server.is_any_device_found.return_value = False
    # A plain function, not a MagicMock: see test_user_flow_creates_entry.
    # Needed on the retry cycle below in particular, where
    # is_any_device_found() is already True before the search even starts.
    mock_home_server.searchDevices = lambda: None

    with patch(
        "homeassistant.components.hausbus.config_flow._DEVICE_SEARCH_TIMEOUT",
        0.01,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "wait_for_device"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "search_timeout"

        mock_home_server.is_any_device_found.return_value = True

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "wait_for_device"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_os_error_shows_search_timeout(
    hass: HomeAssistant,
) -> None:
    """Test that a failure to construct/use the HomeServer is treated as a timeout."""

    def _raise_os_error() -> NoReturn:
        raise OSError

    # `new=` rather than `side_effect=`: hass's test-mode executor-job
    # runner special-cases a Mock target and runs it inline instead of on
    # a worker thread. Left as a Mock, this failure - and the flow
    # cascading past SHOW_PROGRESS straight to the search_timeout step -
    # would complete synchronously within the first async_configure() call
    # below, which then feeds that call's own user_input={} right back
    # into async_step_search_timeout() as if it were a resubmission,
    # looping the flow between wait_for_device and search_timeout forever.
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        new=_raise_os_error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "wait_for_device"

        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "search_timeout"


async def test_single_instance_allowed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that only one config entry is allowed."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_flow_removal_waits_for_active_search_before_releasing(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
) -> None:
    """Aborting a flow waits for its in-flight search before releasing the HomeServer.

    searchDevices() must be a real function, not a MagicMock: hass's
    test-mode executor job runner special-cases Mock targets and runs them
    inline, leaving nothing still running to cancel into.
    """
    search_started = threading.Event()
    release_search = threading.Event()

    def _slow_search_devices() -> None:
        search_started.set()
        assert release_search.wait(timeout=5), "test did not release in time"

    mock_home_server.searchDevices = _slow_search_devices

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "wait_for_device"

    # Wait until searchDevices() has actually started on the executor, so
    # aborting below lands while it is genuinely still running.
    assert await hass.async_add_executor_job(search_started.wait, 5)

    hass.config_entries.flow.async_abort(result["flow_id"])

    # The removal's cleanup awaits the cancelled search task, which cannot
    # actually finish until the still-running searchDevices() call
    # returns - so the HomeServer must not be released yet.
    await asyncio.sleep(0.1)
    mock_home_server.shutdown.assert_not_called()

    release_search.set()

    await hass.async_block_till_done(wait_background_tasks=True)

    mock_home_server.shutdown.assert_called_once()
