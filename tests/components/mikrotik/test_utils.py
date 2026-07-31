"""Test Mikrotik utils."""

from librouteros.exceptions import ConnectionClosed, LibRouterosError
import pytest

from homeassistant.components.mikrotik.errors import CannotConnect, LoginError
from homeassistant.components.mikrotik.utils import mikrotik_config_entry_errors
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.update_coordinator import UpdateFailed


def test_login_error_raises_config_entry_auth_failed() -> None:
    """Test a login error is translated to ConfigEntryAuthFailed."""
    with (
        pytest.raises(ConfigEntryAuthFailed) as exc_info,
        mikrotik_config_entry_errors(),
    ):
        raise LoginError

    assert exc_info.value.translation_key == "invalid_auth"


@pytest.mark.parametrize(
    "error",
    [
        CannotConnect(),
        OSError(),
        TimeoutError(),
        ConnectionClosed(),
    ],
    ids=["cannot_connect", "os_error", "timeout_error", "connection_closed"],
)
@pytest.mark.parametrize(
    ("during_setup", "expected_exception"),
    [
        pytest.param(True, ConfigEntryNotReady, id="during_setup"),
        pytest.param(False, UpdateFailed, id="during_update"),
    ],
)
def test_connection_error_raises_expected_exception(
    error: Exception,
    during_setup: bool,
    expected_exception: type[Exception],
) -> None:
    """Test connectivity errors raise ConfigEntryNotReady or UpdateFailed."""
    with (
        pytest.raises(expected_exception) as exc_info,
        mikrotik_config_entry_errors(during_setup=during_setup),
    ):
        raise error

    assert exc_info.value.translation_key == "cannot_connect"


@pytest.mark.parametrize(
    ("suppress_errors", "message"),
    [
        pytest.param(False, "no such command prefix", id="not_suppressed"),
        pytest.param(True, "some other error", id="suppressed_other_message"),
    ],
)
def test_api_error_raises_home_assistant_error(
    suppress_errors: bool, message: str
) -> None:
    """Test a LibRouterosError raises HomeAssistantError unless suppressed."""
    with (
        pytest.raises(HomeAssistantError) as exc_info,
        mikrotik_config_entry_errors(suppress_errors=suppress_errors),
    ):
        raise LibRouterosError(message)

    assert exc_info.value.translation_key == "mikrotik_api_error"


def test_suppressed_api_error_is_suppressed() -> None:
    """Test suppress_errors suppresses the 'no such command prefix' error."""
    with mikrotik_config_entry_errors(suppress_errors=True):
        raise LibRouterosError("no such command prefix")
