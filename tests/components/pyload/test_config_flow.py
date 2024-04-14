"""Test the pyLoad config flow."""

from unittest.mock import AsyncMock

from pyloadapi.exceptions import CannotConnect, InvalidAuth, ParserError
import pytest

from homeassistant import config_entries
from homeassistant.components.pyload.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.issue_registry as ir

from .conftest import TEST_USER_DATA

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pyloadapi: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_USER_DATA[CONF_HOST]}:{TEST_USER_DATA[CONF_PORT]}"
    assert result["data"] == TEST_USER_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CannotConnect(), "cannot_connect"),
        (InvalidAuth(), "invalid_auth"),
        (ParserError(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_error_and_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pyloadapi: AsyncMock,
    raise_error,
    text_error,
) -> None:
    """Test we handle invalid auth."""
    mock_pyloadapi.login.side_effect = raise_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_pyloadapi.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_USER_DATA[CONF_HOST]}:{TEST_USER_DATA[CONF_PORT]}"
    assert result["data"] == TEST_USER_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_user_already_configured(
    hass: HomeAssistant,
    mock_pyloadapi: AsyncMock,
    pyload_config_entry: MockConfigEntry,
) -> None:
    """Test we abort user data set when entry is already configured."""

    pyload_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_reauth(
    hass: HomeAssistant,
    mock_pyloadapi: AsyncMock,
    pyload_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""

    pyload_config_entry.add_to_hass(hass)
    assert pyload_config_entry.data == TEST_USER_DATA
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": pyload_config_entry.entry_id,
            "unique_id": pyload_config_entry.unique_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-username", CONF_PASSWORD: "new-password"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert pyload_config_entry.data == {
        **TEST_USER_DATA,
        CONF_PASSWORD: "new-password",
        CONF_USERNAME: "new-username",
    }


async def test_flow_import(hass: HomeAssistant, mock_pyloadapi: AsyncMock) -> None:
    """Test that we can import a YAML config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_HOST: TEST_USER_DATA[CONF_HOST],
            CONF_PASSWORD: TEST_USER_DATA[CONF_PASSWORD],
            CONF_PORT: TEST_USER_DATA[CONF_PORT],
            CONF_SSL: TEST_USER_DATA[CONF_SSL],
            CONF_USERNAME: TEST_USER_DATA[CONF_USERNAME],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{TEST_USER_DATA[CONF_HOST]}:{TEST_USER_DATA[CONF_PORT]}"
    assert result["data"] == TEST_USER_DATA

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "deprecated_yaml_pyload"
    )
    assert issue.translation_key == "deprecated_yaml"


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CannotConnect(), "cannot_connect"),
        (InvalidAuth(), "invalid_auth"),
        (ParserError(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_import_error(
    hass: HomeAssistant, mock_pyloadapi: AsyncMock, raise_error, text_error
) -> None:
    """Test that we can import a YAML config."""

    mock_pyloadapi.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_HOST: TEST_USER_DATA[CONF_HOST],
            CONF_PASSWORD: TEST_USER_DATA[CONF_PASSWORD],
            CONF_PORT: TEST_USER_DATA[CONF_PORT],
            CONF_SSL: TEST_USER_DATA[CONF_SSL],
            CONF_USERNAME: TEST_USER_DATA[CONF_USERNAME],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{text_error}"
    )
    assert issue.translation_key == f"deprecated_yaml_import_issue_{text_error}"


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CannotConnect(), "cannot_connect"),
        (InvalidAuth(), "invalid_auth"),
        (ParserError(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_reauth_error_and_recover(
    hass: HomeAssistant,
    mock_pyloadapi: AsyncMock,
    pyload_config_entry: MockConfigEntry,
    raise_error,
    text_error,
) -> None:
    """Test reauth flow."""

    pyload_config_entry.add_to_hass(hass)
    assert pyload_config_entry.data == TEST_USER_DATA
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": pyload_config_entry.entry_id,
            "unique_id": pyload_config_entry.unique_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_pyloadapi.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password", CONF_USERNAME: "new-username"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}
    assert pyload_config_entry.data == TEST_USER_DATA

    mock_pyloadapi.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password", CONF_USERNAME: "new-username"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
    assert pyload_config_entry.data == {
        **TEST_USER_DATA,
        CONF_PASSWORD: "new-password",
        CONF_USERNAME: "new-username",
    }


async def test_flow_reconfigure(
    hass: HomeAssistant,
    mock_pyloadapi: AsyncMock,
    pyload_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""

    pyload_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": pyload_config_entry.entry_id,
            "unique_id": pyload_config_entry.unique_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_DATA
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert pyload_config_entry.data == TEST_USER_DATA


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CannotConnect(), "cannot_connect"),
        (InvalidAuth(), "invalid_auth"),
        (ParserError(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_reconfigure_error_and_recover(
    hass: HomeAssistant,
    mock_pyloadapi: AsyncMock,
    pyload_config_entry: MockConfigEntry,
    raise_error,
    text_error,
) -> None:
    """Test reauth flow."""

    pyload_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": pyload_config_entry.entry_id,
            "unique_id": pyload_config_entry.unique_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    mock_pyloadapi.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TEST_USER_DATA, CONF_HOST: "2.2.2.2"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}
    assert pyload_config_entry.data == TEST_USER_DATA

    mock_pyloadapi.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TEST_USER_DATA, CONF_HOST: "2.2.2.2"}
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(hass.config_entries.async_entries()) == 1
    assert pyload_config_entry.data == {**TEST_USER_DATA, CONF_HOST: "2.2.2.2"}
