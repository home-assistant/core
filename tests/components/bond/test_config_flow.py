"""Test the Bond config flow."""

from aiohttp import ClientConnectionError, ClientResponseError

from homeassistant import config_entries, core, setup
from homeassistant.components.bond.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

from tests.async_mock import Mock, patch


async def test_form(hass: core.HomeAssistant):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.bond.config_flow.Bond.devices", return_value=[],
    ), patch(
        "homeassistant.components.bond.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.bond.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_ACCESS_TOKEN: "test-token",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: core.HomeAssistant):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bond.config_flow.Bond.devices",
        side_effect=ClientResponseError(Mock(), Mock(), status=401),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: core.HomeAssistant):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bond.config_flow.Bond.devices",
        side_effect=ClientConnectionError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_error(hass: core.HomeAssistant):
    """Test we handle unexpected error gracefully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.bond.config_flow.Bond.devices",
        side_effect=ClientResponseError(Mock(), Mock(), status=500),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
