"""Tests for the mapping of aionanoleaf2 errors in the Nanoleaf config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aionanoleaf2 import (
    AuthError,
    EndpointNotFoundError,
    InvalidResponseError,
    InvalidToken,
    NanoleafConnectionError,
    NanoleafError,
    NanoleafTimeoutError,
    Unauthorized,
    Unavailable,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.nanoleaf.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_NAME = "Canvas ADF9"
TEST_HOST = "192.168.0.100"
TEST_OTHER_HOST = "192.168.0.200"
TEST_TOKEN = "R34F1c92FNv3pcZs4di17RxGqiLSwHM"

# Every library error that means "the device cannot be used right now"
CONNECT_ERRORS = [
    pytest.param(Unavailable("unavailable"), id="unavailable"),
    pytest.param(NanoleafConnectionError("connection"), id="connection"),
    pytest.param(NanoleafTimeoutError("timeout"), id="timeout"),
    pytest.param(InvalidResponseError("response"), id="invalid_response"),
    pytest.param(EndpointNotFoundError("new"), id="endpoint_not_found"),
    pytest.param(NanoleafError("generic"), id="generic"),
]

AUTH_ERRORS = [
    pytest.param(InvalidToken("invalid"), id="invalid_token"),
    pytest.param(AuthError("auth"), id="auth_error"),
]


def _mock_nanoleaf(
    host: str = TEST_HOST,
    authorize_error: Exception | None = None,
    get_info_error: Exception | None = None,
) -> MagicMock:
    nanoleaf = MagicMock()
    nanoleaf.name = TEST_NAME
    nanoleaf.host = host
    nanoleaf.auth_token = TEST_TOKEN
    nanoleaf.authorize = AsyncMock(side_effect=authorize_error)
    nanoleaf.get_info = AsyncMock(side_effect=get_info_error)
    return nanoleaf


@pytest.mark.parametrize("error", CONNECT_ERRORS)
async def test_user_step_library_error_shows_cannot_connect(
    hass: HomeAssistant, error: NanoleafError
) -> None:
    """Test every library error in the user step is shown as cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(authorize_error=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # pylint: disable-next=home-assistant-tests-config-flow-error-recovery
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"


async def test_user_step_unauthorized_continues_with_link_step(
    hass: HomeAssistant,
) -> None:
    """Test a device that is not in pairing mode still reaches the link step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(authorize_error=Unauthorized("pairing")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"
    assert result["errors"] is None


@pytest.mark.parametrize("error", CONNECT_ERRORS)
async def test_link_step_library_error_aborts_with_cannot_connect(
    hass: HomeAssistant, error: NanoleafError
) -> None:
    """Test every library error in the link step aborts with cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(),
    ) as mock_nanoleaf:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
        assert result["step_id"] == "link"

        mock_nanoleaf.return_value.authorize.side_effect = error
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        *[pytest.param(e.values[0], "cannot_connect", id=e.id) for e in CONNECT_ERRORS],
        *[pytest.param(e.values[0], "invalid_token", id=e.id) for e in AUTH_ERRORS],
    ],
)
async def test_setup_finish_library_error_aborts(
    hass: HomeAssistant, error: NanoleafError, reason: str
) -> None:
    """Test library errors while reading the device info abort with a reason."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(get_info_error=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_HOST}
        )
        assert result["step_id"] == "link"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize("error", CONNECT_ERRORS)
async def test_reauth_library_error_aborts_with_cannot_connect(
    hass: HomeAssistant, error: NanoleafError
) -> None:
    """Test a library error while requesting a new token aborts the reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_NAME,
        data={CONF_HOST: TEST_HOST, CONF_TOKEN: "old-token"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
        return_value=_mock_nanoleaf(authorize_error=error),
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "link"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert entry.data[CONF_TOKEN] == "old-token"


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        *[pytest.param(e.values[0], "cannot_connect", id=e.id) for e in CONNECT_ERRORS],
        *[pytest.param(e.values[0], "invalid_token", id=e.id) for e in AUTH_ERRORS],
    ],
)
async def test_reconfigure_library_errors_and_recovery(
    hass: HomeAssistant, error: NanoleafError, expected_error: str
) -> None:
    """Test library errors while reconfiguring are shown and can be recovered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_NAME,
        data={CONF_HOST: TEST_HOST, CONF_TOKEN: TEST_TOKEN},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.nanoleaf.config_flow.Nanoleaf",
            return_value=_mock_nanoleaf(TEST_OTHER_HOST, get_info_error=error),
        ) as mock_nanoleaf,
        patch(
            "homeassistant.components.nanoleaf.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_OTHER_HOST}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert result["errors"] == {"base": expected_error}
        assert entry.data[CONF_HOST] == TEST_HOST

        mock_nanoleaf.return_value.get_info.side_effect = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: TEST_OTHER_HOST}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: TEST_OTHER_HOST, CONF_TOKEN: TEST_TOKEN}
