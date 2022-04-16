"""Define tests for the QNAP QSW config flow."""

from unittest.mock import MagicMock, patch

from aioqsw.const import API_RESULT, API_SERIAL
from aioqsw.exceptions import LoginError, QswError

from homeassistant import data_entry_flow
from homeassistant.components.qnap_qsw.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .util import CONFIG, LIVE_MOCK, SYSTEM_BOARD_MOCK, USERS_LOGIN_MOCK

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test that the form is served with valid input."""

    with patch(
        "homeassistant.components.qnap_qsw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_live",
        return_value=LIVE_MOCK,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.get_system_board",
        return_value=SYSTEM_BOARD_MOCK,
    ), patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.post_users_login",
        return_value=USERS_LOGIN_MOCK,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert (
            result["title"] == f"QNAP QSW {SYSTEM_BOARD_MOCK[API_RESULT][API_SERIAL]}"
        )
        assert result["data"][CONF_URL] == CONFIG[CONF_URL]
        assert result["data"][CONF_USERNAME] == CONFIG[CONF_USERNAME]
        assert result["data"][CONF_PASSWORD] == CONFIG[CONF_PASSWORD]

        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicated_id(hass: HomeAssistant) -> None:
    """Test setting up duplicated entry."""

    system_board = MagicMock()
    system_board.get_serial = MagicMock(
        return_value=SYSTEM_BOARD_MOCK[API_RESULT][API_SERIAL]
    )

    entry = MockConfigEntry(
        domain=DOMAIN, data=CONFIG, unique_id=SYSTEM_BOARD_MOCK[API_RESULT][API_SERIAL]
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.validate",
        return_value=system_board,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_connection_error(hass: HomeAssistant):
    """Test connection to host error."""

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.validate",
        side_effect=QswError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_login_error(hass: HomeAssistant):
    """Test login error."""

    with patch(
        "homeassistant.components.qnap_qsw.QnapQswApi.validate",
        side_effect=LoginError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "invalid_auth"}
