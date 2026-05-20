"""Fixtures for the Leviton Decora Wi-Fi integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.decora_wifi.const import DOMAIN

from .const import TEST_USER_ID, TEST_USERNAME, USER_INPUT

from tests.common import MockConfigEntry


def _build_mock_switch(
    serial: str = "AA:BB:CC:DD:EE:FF",
    name: str = "Living Room",
    can_set_level: bool = True,
    brightness: int = 80,
    power: str = "ON",
) -> MagicMock:
    """Build a mock IoT switch."""
    switch = MagicMock()
    switch.serial = serial
    switch.name = name
    switch.canSetLevel = can_set_level
    switch.brightness = brightness
    switch.power = power
    switch.data = {"minLevel": 0, "maxLevel": 100}
    return switch


@pytest.fixture
def mock_switch() -> MagicMock:
    """Return a mock IoT switch."""
    return _build_mock_switch()


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_USERNAME,
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=TEST_USER_ID,
    )


@pytest.fixture
def mock_person() -> Generator[MagicMock]:
    """Mock Person at library level for both __init__ and config_flow."""
    with (
        patch("homeassistant.components.decora_wifi.Person") as mock_cls,
        patch(
            "homeassistant.components.decora_wifi.config_flow.Person",
            new=mock_cls,
        ),
    ):
        yield mock_cls


@pytest.fixture
def mock_residence(mock_switch: MagicMock) -> Generator[MagicMock]:
    """Mock Residence and ResidentialAccount at library level."""
    with (
        patch(
            "homeassistant.components.decora_wifi.Residence",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.decora_wifi.ResidentialAccount",
        ),
    ):
        mock_cls.return_value.get_iot_switches.return_value = [mock_switch]
        yield mock_cls.return_value


@pytest.fixture
def mock_decora_wifi(
    mock_switch: MagicMock,
    mock_person: MagicMock,
    mock_residence: MagicMock,
) -> Generator[MagicMock]:
    """Mock DecoraWiFiSession at library level for both __init__ and config_flow."""
    with (
        patch(
            "homeassistant.components.decora_wifi.DecoraWiFiSession",
        ) as mock_cls,
        patch(
            "homeassistant.components.decora_wifi.config_flow.DecoraWiFiSession",
            new=mock_cls,
        ),
    ):
        mock_session = mock_cls.return_value
        mock_session.user._id = TEST_USER_ID
        mock_session.login.return_value = True

        permission = MagicMock()
        permission.residentialAccountId = None
        permission.residenceId = "res-1"
        mock_session.user.get_residential_permissions.return_value = [permission]

        yield mock_session


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.decora_wifi.async_setup_entry", return_value=True
    ) as mock_fn:
        yield mock_fn
