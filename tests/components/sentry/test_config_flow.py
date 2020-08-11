"""Test the sentry config flow."""
from sentry_sdk.utils import BadDsn

from homeassistant import config_entries, setup
from homeassistant.components.sentry.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sentry.config_flow.validate_input",
        return_value={"title": "Sentry"},
    ), patch(
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


async def test_form_bad_dsn(hass):
    """Test we handle bad dsn error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.sentry.config_flow.validate_input",
        side_effect=BadDsn,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"dsn": "foo"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "bad_dsn"}
