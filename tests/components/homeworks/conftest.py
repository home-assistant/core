"""Common fixtures for the Lutron Homeworks Series 4 and 8 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.homeworks.const import (
    CONF_ADDR,
    CONF_BUTTONS,
    CONF_CONTROLLER_ID,
    CONF_DIMMERS,
    CONF_KEYPADS,
    CONF_LED,
    CONF_NUMBER,
    CONF_RATE,
    CONF_RELEASE_DELAY,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

CONFIG_ENTRY_OPTIONS = {
    CONF_CONTROLLER_ID: "main_controller",
    CONF_HOST: "192.168.0.1",
    CONF_PORT: 1234,
    CONF_DIMMERS: [
        {
            CONF_ADDR: "[02:08:01:01]",
            CONF_NAME: "Foyer Sconces",
            CONF_RATE: 1.0,
        }
    ],
    CONF_KEYPADS: [
        {
            CONF_ADDR: "[02:08:02:01]",
            CONF_NAME: "Foyer Keypad",
            CONF_BUTTONS: [
                {
                    CONF_NAME: "Morning",
                    CONF_NUMBER: 1,
                    CONF_LED: True,
                    CONF_RELEASE_DELAY: None,
                },
                {
                    CONF_NAME: "Relax",
                    CONF_NUMBER: 2,
                    CONF_LED: True,
                    CONF_RELEASE_DELAY: None,
                },
                {
                    CONF_NAME: "Dim up",
                    CONF_NUMBER: 3,
                    CONF_LED: False,
                    CONF_RELEASE_DELAY: 0.2,
                },
            ],
        }
    ],
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Lutron Homeworks",
        domain=DOMAIN,
        data={CONF_PASSWORD: None, CONF_USERNAME: None},
        options=CONFIG_ENTRY_OPTIONS,
    )


@pytest.fixture
def mock_config_entry_username_password() -> MockConfigEntry:
    """Return the default mocked config entry with credentials."""
    return MockConfigEntry(
        title="Lutron Homeworks",
        domain=DOMAIN,
        data={CONF_PASSWORD: "hunter2", CONF_USERNAME: "username"},
        options=CONFIG_ENTRY_OPTIONS,
    )


@pytest.fixture
def mock_empty_config_entry() -> MockConfigEntry:
    """Return a mocked config entry with no keypads or dimmers."""
    return MockConfigEntry(
        title="Lutron Homeworks",
        domain=DOMAIN,
        data={},
        options={
            CONF_CONTROLLER_ID: "main_controller",
            CONF_HOST: "192.168.0.1",
            CONF_PORT: 1234,
            CONF_DIMMERS: [],
            CONF_KEYPADS: [],
        },
    )


@pytest.fixture
def mock_homeworks() -> Generator[MagicMock]:
    """Return a mocked Homeworks client."""
    with (
        patch(
            "homeassistant.components.homeworks.Homeworks", autospec=True
        ) as homeworks_mock,
        patch(
            "homeassistant.components.homeworks.config_flow.Homeworks",
            new=homeworks_mock,
        ),
    ):
        yield homeworks_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.homeworks.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
