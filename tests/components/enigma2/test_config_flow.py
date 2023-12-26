"""Test the Enigma2 config flow."""
from typing import Any
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


@pytest.mark.parametrize(
    ("test_config", "expected_title"),
    [(TEST_FULL, TEST_FULL[CONF_NAME]), (TEST_REQUIRED, TEST_REQUIRED[CONF_HOST])],
)
async def test_form_user(
    hass: HomeAssistant, user_flow, test_config: dict[str, Any], expected_title: str
):
    """Test a successful user initiated flow."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        return_value=MockDevice(),
    ), patch(
        "homeassistant.components.enigma2.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(user_flow, test_config)
        await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["title"] == expected_title
    assert result["options"] == test_config

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (InvalidAuthError, "invalid_auth"),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_user_errors(
    hass: HomeAssistant, user_flow, exception: Exception, error_type: str
) -> None:
    """Test we handle errors."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(user_flow, TEST_FULL)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error_type}


@pytest.mark.parametrize(
    ("test_config", "expected_title", "expected_options"),
    [
        (TEST_IMPORT_FULL, TEST_IMPORT_FULL[CONF_NAME], TEST_IMPORT_FULL),
        (TEST_IMPORT_REQUIRED, TEST_REQUIRED[CONF_HOST], TEST_REQUIRED),
    ],
)
async def test_form_import(
    hass: HomeAssistant,
    test_config: dict[str, Any],
    expected_title: str,
    expected_options: dict[str, Any],
) -> None:
    """Test we get the form with import source."""
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
            data=test_config,
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == expected_title
    assert result["options"] == expected_options

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (InvalidAuthError, "invalid_auth"),
        (ClientError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_import_errors(
    hass: HomeAssistant, exception: Exception, error_type: str
) -> None:
    """Test we handle errors on import."""
    with patch(
        "openwebif.api.OpenWebIfDevice.__new__",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=TEST_IMPORT_FULL,
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": error_type}
