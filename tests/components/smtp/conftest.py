"""Common fixtures for the SMTP tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.smtp.const import (
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_SENDER: "email@example.com",
    CONF_SENDER_NAME: "Home Assistant",
    CONF_SERVER: "mail.example.com",
    CONF_PORT: 587,
    CONF_ENCRYPTION: "starttls",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_VERIFY_SSL: True,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smtp.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="smtp")
def mock_smtp() -> Generator[MagicMock]:
    """Mock smtplib.SMTP."""

    with (
        patch(
            "homeassistant.components.smtp.config_flow.SMTP_SSL", autospec=True
        ) as mock_client,
        patch("homeassistant.components.smtp.helpers.smtplib.SMTP", new=mock_client),
        patch("homeassistant.components.smtp.config_flow.SMTP", new=mock_client),
    ):
        client = mock_client.return_value
        client.cls = mock_client
        yield client


@pytest.fixture(name="make_msgid")
def mock_make_msgid() -> Generator[None]:
    """Mock email.utils.make_msgid."""

    with patch(
        "homeassistant.components.smtp.notify.email.utils.make_msgid",
        return_value="<177777777700.12345.12345678901234567890@mock>",
    ):
        yield


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock smtp configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant",
        data=USER_INPUT,
        options={
            CONF_TIMEOUT: 1312,
        },
        entry_id="123456789",
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_id="ABCDEF",
                subentry_type=SUBENTRY_TYPE_RECIPIENT,
                title="Recipient",
                unique_id="recipient@example.com",
            )
        ],
    )
