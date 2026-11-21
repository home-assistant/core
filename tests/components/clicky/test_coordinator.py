"""Tests for the Clicky coordinator."""

import asyncio
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
from pyclicky import AuthenticationError, ClickyAPIError, ConnectionError, Report
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.clicky.const import (
    CONF_SITE_ID,
    CONF_SITEKEY,
    DOMAIN,
    UPDATE_INTERVAL,
)
from homeassistant.components.clicky.coordinator import ClickyCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .common import _make_empty_report, _make_report
from .const import TEST_SITE_ID, TEST_SITEKEY


def test_coordinator_init(hass: HomeAssistant) -> None:
    """Test coordinator initialization."""

    entry = Mock()
    client = Mock()

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
    )

    assert coordinator.client is client
    assert coordinator.name == DOMAIN
    assert coordinator.update_interval == timedelta(minutes=1)


@pytest.mark.asyncio
async def test_async_update_data_auth_failure(hass: HomeAssistant) -> None:
    """Test that authentication errors become ConfigEntryAuthFailed."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.side_effect = AuthenticationError

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    with pytest.raises(ConfigEntryAuthFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_auth"


@pytest.mark.asyncio
async def test_async_update_data_connection_error(hass: HomeAssistant) -> None:
    """Test that connection errors become UpdateFailed."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.side_effect = ConnectionError("Connection refused")

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "cannot_connect"
    assert exc_info.value.translation_placeholders is None
    assert exc_info.value.__cause__ is client.visitors_online.side_effect


async def test_http_error_hides_sitekey(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that HTTP errors don't leak the sitekey into logged tracebacks."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: TEST_SITE_ID,
            CONF_SITEKEY: TEST_SITEKEY,
        },
    )
    entry.add_to_hass(hass)

    # pyclicky passes the sitekey as a query parameter and does not wrap
    # ClientResponseError, whose string form includes the full request URL.
    http_error = ClientResponseError(
        Mock(
            real_url=(
                "https://api.clicky.com/api/stats/4"
                f"?site_id={TEST_SITE_ID}&sitekey={TEST_SITEKEY}"
            )
        ),
        (),
        status=500,
        message="Internal Server Error",
    )
    assert TEST_SITEKEY in str(http_error)

    with (
        patch(
            "pyclicky.ClickyClient.visitors_online",
            AsyncMock(return_value=_make_report(5)),
        ) as mock_visitors_online,
        patch(
            "pyclicky.ClickyClient.time_total",
            AsyncMock(return_value=_make_report(120)),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data
        assert coordinator.last_update_success

        mock_visitors_online.side_effect = http_error
        caplog.set_level(logging.DEBUG)

        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.translation_key == "cannot_connect"
    assert coordinator.last_exception.__cause__ is None
    assert coordinator.last_exception.__suppress_context__
    assert caplog.records
    assert TEST_SITEKEY not in caplog.text


@pytest.mark.asyncio
async def test_async_update_data_request_timeout(hass: HomeAssistant) -> None:
    """Test that a hanging request times out and becomes UpdateFailed."""

    async def _hang(**kwargs: Any) -> None:
        await asyncio.Event().wait()

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.side_effect = _hang

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    with (
        patch("homeassistant.components.clicky.coordinator.REQUEST_TIMEOUT", 0),
        pytest.raises(UpdateFailed) as exc_info,
    ):
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "cannot_connect"
    assert isinstance(exc_info.value.__cause__, TimeoutError)


@pytest.mark.asyncio
async def test_async_update_data_success(hass: HomeAssistant) -> None:
    """Test successful update."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.return_value = _make_report(12)
    client.time_total.return_value = _make_report(345)

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    data = await coordinator._async_update_data()

    assert data == {
        "visitorsOnline": 12,
        "timeTotal": 345,
    }

    assert client.visitors_online.await_count == 1
    assert client.time_total.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("visitors_online_report", "time_total_report", "expected"),
    [
        (
            _make_empty_report(),
            _make_report(345),
            {"visitorsOnline": 0, "timeTotal": 345},
        ),
        (
            _make_report(12),
            _make_empty_report(),
            {"visitorsOnline": 12, "timeTotal": 0},
        ),
    ],
    ids=["visitors_online_empty", "time_total_empty"],
)
async def test_async_update_data_empty_report(
    hass: HomeAssistant,
    visitors_online_report: Report,
    time_total_report: Report,
    expected: dict[str, int],
) -> None:
    """Test that a report without a value falls back to zero."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.return_value = visitors_online_report
    client.time_total.return_value = time_total_report

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    assert await coordinator._async_update_data() == expected


@pytest.mark.asyncio
async def test_async_update_data_failure(hass: HomeAssistant) -> None:
    """Test that API errors become UpdateFailed."""

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None

    client.visitors_online.side_effect = ClickyAPIError("Unexpected Error")

    coordinator = ClickyCoordinator(
        hass=hass,
        config_entry=Mock(),
        client=client,
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "api_error"
    assert exc_info.value.translation_placeholders is None
    assert exc_info.value.__cause__ is client.visitors_online.side_effect
