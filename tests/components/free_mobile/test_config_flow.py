"""Test the Free Mobile config flow."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.free_mobile.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_send_sms() -> Generator[MagicMock]:
    """Mock the Free Mobile SMS client's send_sms call."""
    with patch("freesms.FreeClient.send_sms") as mock:
        mock.return_value = MagicMock(status_code=HTTPStatus.OK)
        yield mock


async def test_flow_user(hass: HomeAssistant, mock_send_sms: MagicMock) -> None:
    """Test user initialized flow creates an entry titled after the username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG[CONF_USERNAME]
    assert result["data"] == MOCK_CONFIG


async def test_flow_user_username_already_configured(hass: HomeAssistant) -> None:
    """Test the user flow aborts if the username is already configured."""
    MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MOCK_CONFIG, CONF_ACCESS_TOKEN: "another-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("status_code", "error_key"),
    [
        pytest.param(HTTPStatus.FORBIDDEN, "invalid_auth", id="invalid_auth"),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR, "server_error", id="server_error"
        ),
    ],
)
async def test_flow_user_validation_error(
    hass: HomeAssistant,
    mock_send_sms: MagicMock,
    status_code: HTTPStatus,
    error_key: str,
) -> None:
    """Test the user flow shows an error when credential validation fails, then recovers."""
    mock_send_sms.return_value = MagicMock(status_code=status_code)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    mock_send_sms.return_value = MagicMock(status_code=HTTPStatus.OK)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_user_validation_unknown_error(
    hass: HomeAssistant, mock_send_sms: MagicMock
) -> None:
    """Test the user flow shows an unknown error when send_sms raises, then recovers."""
    mock_send_sms.side_effect = Exception("unexpected")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_send_sms.side_effect = None
    mock_send_sms.return_value = MagicMock(status_code=HTTPStatus.OK)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_import_dedup_by_title_same_name_is_rejected(
    hass: HomeAssistant,
) -> None:
    """Test importing the same title twice is rejected, even with a shared username."""
    first_import = {**MOCK_CONFIG, CONF_NAME: "Maman"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=first_import
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maman"

    second_import = {**MOCK_CONFIG, CONF_NAME: "Maman"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=second_import
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_import_dedup_by_title_distinct_name_allows_shared_username(
    hass: HomeAssistant,
) -> None:
    """Test a distinct name allows importing a shared username.

    This preserves legacy multi-account YAML setups where several named
    notify services share the same Free Mobile username.
    """
    first_import = {**MOCK_CONFIG, CONF_NAME: "Maman"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=first_import
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maman"

    second_import = {**MOCK_CONFIG, CONF_NAME: "Papa"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=second_import
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Papa"


async def test_flow_import_no_name_uses_username_as_title(hass: HomeAssistant) -> None:
    """Test import without a name falls back to the username as title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_CONFIG[CONF_USERNAME]
    assert result["data"] == MOCK_CONFIG
