"""Test the sentry config flow."""
from sentry_sdk.utils import BadDsn

from homeassistant.components.sentry.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_FORM
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(hass):
    """Test we get the form."""
    await async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch("homeassistant.components.sentry.config_flow.Dsn"), patch(
        "homeassistant.components.sentry.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.sentry.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"dsn": "http://public@sentry.local/1"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sentry"
    assert result2["data"] == {
        "dsn": "http://public@sentry.local/1",
    }
    await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_flow_bad_dsn(hass):
    """Test we handle bad dsn error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sentry.config_flow.Dsn", side_effect=BadDsn,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"dsn": "foo"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "bad_dsn"}


async def test_user_flow_unkown_exception(hass):
    """Test we handle any unknown exception error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sentry.config_flow.Dsn", side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"dsn": "foo"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}
