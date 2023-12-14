"""Tests for the Aprilaire config flow."""

import logging
from unittest.mock import AsyncMock, Mock, patch

from pyaprilaire.client import AprilaireClient
from pyaprilaire.const import FunctionalDomain
import pytest

from homeassistant.components.aprilaire.config_flow import (
    STEP_USER_DATA_SCHEMA,
    ConfigFlow,
)
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import EventBus, HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.util import uuid as uuid_util


@pytest.fixture
def logger() -> logging.Logger:
    """Return a logger."""
    logger = logging.getLogger()
    logger.propagate = False

    return logger


@pytest.fixture
def client() -> AprilaireClient:
    """Return a mock client."""
    return AsyncMock(AprilaireClient)


@pytest.fixture
def entry_id() -> str:
    """Return a random ID."""
    return uuid_util.random_uuid_hex()


@pytest.fixture
def hass() -> HomeAssistant:
    """Return a mock HomeAssistant instance."""
    hass_mock = AsyncMock(HomeAssistant)
    hass_mock.data = {}
    hass_mock.config_entries = AsyncMock(ConfigEntries)
    hass_mock.bus = AsyncMock(EventBus)

    return hass_mock


@pytest.fixture
def config_entry(entry_id: str) -> ConfigEntry:
    """Return a mock config entry."""

    config_entry_mock = AsyncMock(ConfigEntry)
    config_entry_mock.data = {"host": "test123", "port": 123}
    config_entry_mock.entry_id = entry_id

    return config_entry_mock


async def test_user_input_step() -> None:
    """Test the user input step."""

    show_form_mock = Mock()

    config_flow = ConfigFlow()
    config_flow.async_show_form = show_form_mock

    await config_flow.async_step_user(None)

    show_form_mock.assert_called_once_with(
        step_id="user", data_schema=STEP_USER_DATA_SCHEMA
    )


async def test_unique_id_abort() -> None:
    """Test that the flow is aborted if a non-unique ID is provided."""

    show_form_mock = Mock()
    set_unique_id_mock = AsyncMock()
    abort_if_unique_id_configured_mock = Mock(
        side_effect=AbortFlow("already_configured")
    )

    config_flow = ConfigFlow()
    config_flow.async_show_form = show_form_mock
    config_flow.async_set_unique_id = set_unique_id_mock
    config_flow._abort_if_unique_id_configured = abort_if_unique_id_configured_mock

    await config_flow.async_step_user(
        {
            "host": "localhost",
            "port": 7000,
        }
    )

    show_form_mock.assert_called_once_with(
        step_id="user",
        data_schema=STEP_USER_DATA_SCHEMA,
        errors={"base": "already_configured"},
    )


async def test_unique_id_exception(
    caplog: pytest.LogCaptureFixture, logger: logging.Logger
) -> None:
    """Assert that the flow is aborted if the unique ID throws an exception."""

    show_form_mock = Mock()
    set_unique_id_mock = AsyncMock()
    abort_if_unique_id_configured_mock = Mock(side_effect=Exception("test"))

    config_flow = ConfigFlow()
    config_flow.async_show_form = show_form_mock
    config_flow.async_set_unique_id = set_unique_id_mock
    config_flow._abort_if_unique_id_configured = abort_if_unique_id_configured_mock

    with caplog.at_level(logging.INFO, logger=logger.name):
        await config_flow.async_step_user(
            {
                "host": "localhost",
                "port": 7000,
            }
        )

    assert caplog.text != ""

    show_form_mock.assert_called_once_with(
        step_id="user",
        data_schema=STEP_USER_DATA_SCHEMA,
        errors={"base": "test"},
    )


async def test_config_flow_invalid_data(client: AprilaireClient) -> None:
    """Test that the flow is aborted with invalid data."""

    show_form_mock = Mock()
    set_unique_id_mock = AsyncMock()
    abort_if_unique_id_configured_mock = Mock()

    config_flow = ConfigFlow()
    config_flow.async_show_form = show_form_mock
    config_flow.async_set_unique_id = set_unique_id_mock
    config_flow._abort_if_unique_id_configured = abort_if_unique_id_configured_mock

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        await config_flow.async_step_user(
            {
                "host": "localhost",
                "port": 7000,
            }
        )

    client.start_listen.assert_called_once()
    client.wait_for_response.assert_called_once_with(
        FunctionalDomain.IDENTIFICATION, 2, 30
    )
    client.stop_listen.assert_called_once()

    show_form_mock.assert_called_once_with(
        step_id="user",
        data_schema=STEP_USER_DATA_SCHEMA,
        errors={"base": "connection_failed"},
    )


async def test_config_flow_data(client: AprilaireClient) -> None:
    """Test the config flow with valid data."""

    show_form_mock = Mock()
    set_unique_id_mock = AsyncMock()
    abort_if_unique_id_configured_mock = Mock()
    create_entry_mock = Mock()
    sleep_mock = AsyncMock()

    config_flow = ConfigFlow()
    config_flow.async_show_form = show_form_mock
    config_flow.async_set_unique_id = set_unique_id_mock
    config_flow._abort_if_unique_id_configured = abort_if_unique_id_configured_mock
    config_flow.async_create_entry = create_entry_mock

    client.wait_for_response = AsyncMock(return_value={"mac_address": "test"})

    with patch("pyaprilaire.client.AprilaireClient", return_value=client), patch(
        "asyncio.sleep", new=sleep_mock
    ):
        await config_flow.async_step_user(
            {
                "host": "localhost",
                "port": 7000,
            }
        )

    client.start_listen.assert_called_once()
    client.wait_for_response.assert_called_once_with(
        FunctionalDomain.IDENTIFICATION, 2, 30
    )
    client.stop_listen.assert_called_once()
    sleep_mock.assert_awaited_once()

    create_entry_mock.assert_called_once_with(
        title="Aprilaire",
        data={
            "host": "localhost",
            "port": 7000,
        },
    )
