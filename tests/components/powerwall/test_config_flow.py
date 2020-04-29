"""Test the Powerwall config flow."""

from asynctest import patch
from tesla_powerwall import PowerWallUnreachableError

from homeassistant import config_entries, setup
from homeassistant.components.powerwall.const import DOMAIN, POWERWALL_SITE_NAME
from homeassistant.const import CONF_IP_ADDRESS

from .mocks import _mock_powerwall_return_value, _mock_powerwall_side_effect


async def test_form_source_user(hass):
    """Test we get config flow setup form as a user."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerwall = _mock_powerwall_return_value(
        site_info={POWERWALL_SITE_NAME: "My site"}
    )

    with patch(
        "homeassistant.components.powerwall.config_flow.PowerWall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.powerwall.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "1.2.3.4"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "My site"
    assert result2["data"] == {CONF_IP_ADDRESS: "1.2.3.4"}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_source_import(hass):
    """Test we setup the config entry via import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_powerwall = _mock_powerwall_return_value(
        site_info={POWERWALL_SITE_NAME: "Imported site"}
    )

    with patch(
        "homeassistant.components.powerwall.config_flow.PowerWall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.powerwall.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_IP_ADDRESS: "1.2.3.4"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Imported site"
    assert result["data"] == {CONF_IP_ADDRESS: "1.2.3.4"}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(site_info=PowerWallUnreachableError)

    with patch(
        "homeassistant.components.powerwall.config_flow.PowerWall",
        return_value=mock_powerwall,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
