"""Test the jellyfin config flow."""
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.jellyfin.config_flow import CannotConnect
from homeassistant.components.jellyfin.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_abort_if_existing_entry(hass):
    """Check flow abort when an entry already exist."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_form(hass):
    """Test the complete configuration form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    url = "https://example.com"
    username = "test-username"
    password = "test-password"

    with patch(
        "homeassistant.components.jellyfin.config_flow.validate_input",
        return_value=url,
    ) as mock_authenticate, patch(
        "homeassistant.components.jellyfin.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.jellyfin.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: url,
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == url
    assert result2["data"] == {
        CONF_URL: url,
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
    }

    assert len(mock_authenticate.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.jellyfin.authenticate",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://example.com",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}