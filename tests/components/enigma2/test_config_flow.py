"""Test the Enigma2 config flow."""
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
from openwebif.error import InvalidAuthError
import pytest

from homeassistant import config_entries
from homeassistant.components.enigma2.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from .util import (
    TEST_FULL,
    TEST_IMPORT_FULL,
    TEST_IMPORT_REQUIRED,
    TEST_REQUIRED,
    MockDevice,
)


@pytest.fixture
async def user_flow(hass):
    """Return a user-initiated flow after filling in host info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    return result["flow_id"]


async def test_full_user_flow(hass: HomeAssistant, user_flow):
    """Test a successful user initiated flow with full config."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ), patch(
        "homeassistant.components.enigma2.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_FULL)
        await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["title"] == TEST_FULL[CONF_NAME]
    assert result["options"] == TEST_FULL

    assert len(mock_setup_entry.mock_calls) == 1


async def test_required_user_flow(hass: HomeAssistant, user_flow) -> None:
    """Test a successful user initiated flow with only required options."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ), patch(
        "homeassistant.components.enigma2.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            user_flow, TEST_REQUIRED
        )
        await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["title"] == TEST_REQUIRED[CONF_HOST]
    assert result["options"] == TEST_REQUIRED

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant, user_flow) -> None:
    """Test we handle invalid auth."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        side_effect=InvalidAuthError(),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_FULL)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect_http(hass: HomeAssistant, user_flow) -> None:
    """Test we handle cannot connect over HTTP error."""
    with patch(
        "tests.components.enigma2.util.MockDevice.get_about",
        side_effect=ClientError(),
    ), patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_FULL)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_exception_http(hass: HomeAssistant, user_flow) -> None:
    """Test we handle generic exception over HTTP."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_FULL)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_form_import_full(hass: HomeAssistant) -> None:
    """Test we get the form with import source, fully configured."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ), patch(
        "homeassistant.components.enigma2.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_IMPORT_FULL,
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_IMPORT_FULL[CONF_NAME]
    assert result["options"] == TEST_IMPORT_FULL

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import_required(hass: HomeAssistant) -> None:
    """Test we get the form with import source with only required values."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ), patch(
        "homeassistant.components.enigma2.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_IMPORT_REQUIRED,
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == TEST_REQUIRED[CONF_HOST]
    assert result["options"] == TEST_REQUIRED

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth on import."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        side_effect=InvalidAuthError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_IMPORT_FULL,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect on import."""
    with patch(
        "tests.components.enigma2.util.MockDevice.get_about",
        side_effect=ClientError(),
    ), patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_IMPORT_FULL,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_import_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exception on import."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_IMPORT_FULL,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}
