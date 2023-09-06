"""Test the sentry config flow."""
import logging
from unittest.mock import patch

from sentry_sdk.utils import BadDsn

from homeassistant.components.sentry.const import (
    CONF_ENVIRONMENT,
    CONF_EVENT_CUSTOM_COMPONENTS,
    CONF_EVENT_HANDLED,
    CONF_EVENT_THIRD_PARTY_PACKAGES,
    CONF_LOGGING_EVENT_LEVEL,
    CONF_LOGGING_LEVEL,
    CONF_TRACING,
    CONF_TRACING_SAMPLE_RATE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    with patch("homeassistant.components.sentry.config_flow.Dsn"), patch(
        "homeassistant.components.sentry.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"dsn": "http://public@sentry.local/1"},
        )

    assert result2.get("type") == "create_entry"
    assert result2.get("title") == "Sentry"
    assert result2.get("data") == {
        "dsn": "http://public@sentry.local/1",
    }
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_already_exists(hass: HomeAssistant) -> None:
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_user_flow_bad_dsn(hass: HomeAssistant) -> None:
    """Test we handle bad dsn error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sentry.config_flow.Dsn",
        side_effect=BadDsn,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"dsn": "foo"},
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "bad_dsn"}


async def test_user_flow_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle any unknown exception error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sentry.config_flow.Dsn",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"dsn": "foo"},
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"dsn": "http://public@sentry.local/1"},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.sentry.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ENVIRONMENT: "Test",
            CONF_EVENT_CUSTOM_COMPONENTS: True,
            CONF_EVENT_HANDLED: True,
            CONF_EVENT_THIRD_PARTY_PACKAGES: True,
            CONF_LOGGING_EVENT_LEVEL: logging.DEBUG,
            CONF_LOGGING_LEVEL: logging.DEBUG,
            CONF_TRACING: True,
            CONF_TRACING_SAMPLE_RATE: 0.5,
        },
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_ENVIRONMENT: "Test",
        CONF_EVENT_CUSTOM_COMPONENTS: True,
        CONF_EVENT_HANDLED: True,
        CONF_EVENT_THIRD_PARTY_PACKAGES: True,
        CONF_LOGGING_EVENT_LEVEL: logging.DEBUG,
        CONF_LOGGING_LEVEL: logging.DEBUG,
        CONF_TRACING: True,
        CONF_TRACING_SAMPLE_RATE: 0.5,
    }
