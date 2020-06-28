"""Test the Plum Lightpad config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.plum_lightpad.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("plumlightpad.Plum.loadCloudData"), patch(
        "homeassistant.components.plum_lightpad.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.plum_lightpad.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-plum-username", "password": "test-plum-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-plum-username"
    assert result2["data"] == {
        "username": "test-plum-username",
        "password": "test-plum-password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import(hass):
    """Test configuring the flow using configuration.yaml."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch("plumlightpad.Plum.loadCloudData"), patch(
        "homeassistant.components.plum_lightpad.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.plum_lightpad.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={"username": "test-plum-username", "password": "test-plum-password"},
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "test-plum-username"
        assert result["data"] == {
            "username": "test-plum-username",
            "password": "test-plum-password",
        }
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
