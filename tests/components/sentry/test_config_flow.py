"""Test the sentry config flow."""
from unittest.mock import patch

from sentry_sdk.utils import BadDsn

from homeassistant import config_entries, setup
from homeassistant.components.sentry.const import CONF_DSN, CONF_ENVIRONMENT, DOMAIN

from tests.common import mock_coro

EXAMPLE_VALID_DSN = "http://public@sentry.local/1"
EXAMPLE_VALID_DSN2 = "http://public@sentry.local/2"


async def test_form_user(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("homeassistant.components.sentry.config_flow.Dsn",), patch(
        "homeassistant.components.sentry.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.sentry.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DSN: EXAMPLE_VALID_DSN},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Sentry"
    assert result["data"] == {
        "dsn": EXAMPLE_VALID_DSN,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_bad_dsn(hass):
    """Test we handle bad dsn error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sentry.config_flow.Dsn", side_effect=BadDsn,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DSN: "foo"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"dsn": "bad_dsn"}


async def test_form_user_duplicate_entries(hass):
    """Test duplicate device or id errors."""
    flow1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sentry.async_setup", return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.sentry.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry, patch(
        "homeassistant.components.sentry.config_flow.Dsn",
    ):
        result1 = await hass.config_entries.flow.async_configure(
            flow1["flow_id"], {CONF_DSN: EXAMPLE_VALID_DSN}
        )
        result2 = await hass.config_entries.flow.async_configure(
            flow2["flow_id"], {CONF_DSN: EXAMPLE_VALID_DSN2}
        )
    assert result1["type"] == "create_entry", result1
    assert result2["type"] == "abort", result2
    assert result2["reason"] == "already_configured", result2
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import(hass):
    """Test import from existing config."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.sentry.async_setup", return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.sentry.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry, patch(
        "homeassistant.components.sentry.config_flow.Dsn",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_DSN: EXAMPLE_VALID_DSN, CONF_ENVIRONMENT: "development"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Sentry"
    assert result["data"] == {"dsn": EXAMPLE_VALID_DSN, "environment": "development"}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
