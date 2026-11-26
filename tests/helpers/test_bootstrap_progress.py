"""Test the bootstrap progress."""

from unittest.mock import Mock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import bootstrap_progress


async def test_subscribe_bootstrap_progress(hass: HomeAssistant) -> None:
    """Test the bootstrap progress is only built and sent for subscribers."""
    progress = {"phase": "setup"}
    source = Mock(return_value=progress)
    first = Mock()
    unsubscribe_first = bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, first
    )
    first.assert_not_called()

    bootstrap_progress._async_set_bootstrap_progress_source(hass, source)
    first.assert_called_once_with(progress)

    # A late subscriber gets the current progress right away.
    second = Mock()
    unsubscribe_second = bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, second
    )
    second.assert_called_once_with(progress)

    unsubscribe_first()
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)
    assert first.call_count == 1
    assert second.call_count == 2
    assert source.call_count == 3

    unsubscribe_second()
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)
    assert second.call_count == 2
    assert source.call_count == 3


async def test_bootstrap_progress_listener_raises(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a listener that raises does not stop the progress for the others."""
    progress = {"phase": "setup"}
    bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, Mock(side_effect=ValueError)
    )
    listener = Mock()
    bootstrap_progress.async_subscribe_bootstrap_progress(hass, listener)

    bootstrap_progress._async_set_bootstrap_progress_source(
        hass, Mock(return_value=progress)
    )

    listener.assert_called_once_with(progress)
    assert "Error sending bootstrap progress to" in caplog.text


async def test_bootstrap_progress_late_listener_raises(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a late listener that raises still gets its unsubscribe callback."""
    bootstrap_progress._async_set_bootstrap_progress_source(
        hass, Mock(return_value={"phase": "setup"})
    )
    listener = Mock(side_effect=ValueError)

    unsubscribe = bootstrap_progress.async_subscribe_bootstrap_progress(hass, listener)

    assert "Error sending bootstrap progress to" in caplog.text
    unsubscribe()
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)
    listener.assert_called_once()


async def test_bootstrap_progress_listener_unsubscribes_itself(
    hass: HomeAssistant,
) -> None:
    """Test a listener unsubscribing itself does not skip the next listener."""
    progress = {"phase": "running"}
    first = Mock(side_effect=lambda _: unsubscribe_first())
    unsubscribe_first = bootstrap_progress.async_subscribe_bootstrap_progress(
        hass, first
    )
    second = Mock()
    bootstrap_progress.async_subscribe_bootstrap_progress(hass, second)

    bootstrap_progress._async_set_bootstrap_progress_source(
        hass, Mock(return_value=progress)
    )
    bootstrap_progress._async_dispatch_bootstrap_progress(hass)

    first.assert_called_once_with(progress)
    assert second.call_count == 2
