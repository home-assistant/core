"""Common fixtures for the SIP Call tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.sipcall.const import CONF_SIP_DOMAIN, CONF_SIP_SERVER
from homeassistant.components.sipcall.notify import SIPCallNotificationService
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sipcall.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def sipcall_notification_service() -> SIPCallNotificationService:
    """Set up sipcall notification service."""

    config = {
        CONF_USERNAME: "myuser",
        CONF_PASSWORD: "mypasword",
        CONF_SIP_DOMAIN: "mysipdomain.com",
        CONF_SIP_SERVER: "mysipserver.com",
    }
    return SIPCallNotificationService(config)


@pytest.fixture
def mock_async_call_and_cancel() -> Generator[AsyncMock, None, None]:
    """Override mock_async_call_and_cancel."""
    with patch(
        "homeassistant.components.sipcall.notify.async_call_and_cancel",
        return_value=None,
    ) as mock_call_cancel:
        yield mock_call_cancel
