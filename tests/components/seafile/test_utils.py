"""Test the Seafile utilities."""

from aioseafile import (
    SeafileConnectionError,
    SeafilePermissionError,
    SeafileTimeoutError,
)
import pytest

from homeassistant.components.seafile.const import DOMAIN
from homeassistant.components.seafile.utils import (
    SeafileErrorHandler,
    handle_seafile_errors,
)
from homeassistant.exceptions import HomeAssistantError


async def test_handle_seafile_errors_returns_result() -> None:
    """Test the result of a successful call is returned."""

    @handle_seafile_errors
    async def call() -> str:
        return "result"

    assert await call() == "result"


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(SeafilePermissionError, "permission_denied", id="not_allowed"),
        pytest.param(SeafileTimeoutError, "timeout_connect", id="timeout"),
        pytest.param(SeafileConnectionError, "api_error", id="failed"),
    ],
)
async def test_handle_seafile_errors(
    exception: type[Exception], translation_key: str
) -> None:
    """Test Seafile errors are raised as translated errors."""

    @handle_seafile_errors
    async def call() -> None:
        raise exception

    with pytest.raises(HomeAssistantError) as exc_info:
        await call()
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == translation_key


async def test_permission_error_without_not_allowed() -> None:
    """Test a permission error is a failure when no translation is set for it."""

    @SeafileErrorHandler(
        HomeAssistantError, DOMAIN, failed="api_error", timed_out="timeout_connect"
    )
    async def call() -> None:
        raise SeafilePermissionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await call()
    assert exc_info.value.translation_key == "api_error"


def test_other_errors_pass_through() -> None:
    """Test errors that are not Seafile errors are not converted."""
    with pytest.raises(ValueError), handle_seafile_errors:
        raise ValueError
