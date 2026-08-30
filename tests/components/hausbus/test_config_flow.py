"""Test the Haus-Bus config flow."""

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
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        side_effect=OSError,
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


async def test_flow_removal_cancels_active_search_task(
    hass: HomeAssistant,
    mock_home_server: MagicMock,
) -> None:
    """Test aborting a flow cancels an active search task.

    Goes through the flow manager's public async_abort() rather than
    calling the flow's async_remove() hook directly, so this also covers
    the manager's own progress-task cancellation (async_cancel_progress_task())
    - not just this integration's private cleanup logic.
    """

    mock_home_server.is_any_device_found.return_value = False

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

    flow = hass.config_entries.flow._progress[result["flow_id"]]

    search_task = flow._search_task

    assert search_task is not None
    assert not search_task.done()

    hass.config_entries.flow.async_abort(result["flow_id"])

    await hass.async_block_till_done()

    assert flow._search_task is None
    assert search_task.cancelled()
    assert flow.home_server is None
