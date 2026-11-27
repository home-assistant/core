"""Fixtures for the KEBA charging station tests."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from keba_kecontact.connection import KebaKeContact
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    load_json_object_fixture,
)

from homeassistant.components.keba.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

HOST = "192.0.2.10"


@pytest.fixture
def expected_lingering_tasks() -> bool:
    """Allow the polling task, which the integration never cancels."""
    return True


@pytest.fixture
def keba_data() -> dict[str, Any]:
    """Return the data the library reports for an idle P30."""
    return load_json_object_fixture("p30.json", DOMAIN)


@pytest.fixture
def mock_keba(
    keba_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> Generator[MagicMock]:
    """Mock the keba-kecontact methods the integration calls."""
    client = MagicMock()
    client.setup = AsyncMock()
    client.get_value = MagicMock(side_effect=keba_data.get)
    client.set_failsafe = AsyncMock()
    client.enable = AsyncMock()
    with (
        patch.multiple(
            KebaKeContact,
            setup=client.setup,
            get_value=client.get_value,
            set_failsafe=client.set_failsafe,
            enable=client.enable,
        ),
        # With autospec the mock gets the handler, and reports the data to it.
        patch.object(
            KebaKeContact,
            "request_data",
            autospec=True,
            side_effect=lambda keba: keba.hass_callback(keba_data),
        ) as request_data,
    ):
        client.request_data = request_data.mock
        yield client


@pytest.fixture
def keba_config() -> dict[str, Any]:
    """Return the YAML configuration for the integration."""
    return {DOMAIN: {CONF_HOST: HOST}}


@pytest.fixture
async def setup_keba(
    hass: HomeAssistant, mock_keba: MagicMock, keba_config: dict[str, Any]
) -> MagicMock:
    """Set up the integration against the mocked library."""
    assert await async_setup_component(hass, DOMAIN, keba_config)
    await async_settle(hass)
    return mock_keba


async def async_settle(hass: HomeAssistant) -> None:
    """Wait until the polling loop has finished its current poll."""
    await hass.async_block_till_done()
    # The loop reschedules itself with loop.create_task, which is not tracked.
    await hass.async_block_till_done()


async def async_advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Move time forward and run the polls that fall due."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await async_settle(hass)


async def async_seconds_until_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_keba: MagicMock,
    limit: int = 60,
) -> int:
    """Move time forward a second at a time and return when the next poll ran."""
    polls_before = mock_keba.request_data.await_count
    for seconds in range(1, limit + 1):
        await async_advance(hass, freezer, 1)
        if mock_keba.request_data.await_count > polls_before:
            return seconds
    pytest.fail(f"No poll within {limit} seconds")
