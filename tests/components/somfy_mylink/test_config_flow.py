"""Test the Somfy MyLink config flow."""
import asyncio
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.somfy_mylink.const import CONF_SYSTEM_ID, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


async def test_form_user(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={"any": "data"},
    ), patch(
        "homeassistant.components.somfy_mylink.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.somfy_mylink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1234,
                CONF_SYSTEM_ID: 456,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "MyLink 1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 1234,
        CONF_SYSTEM_ID: 456,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={"any": "data"},
    ), patch(
        "homeassistant.components.somfy_mylink.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.somfy_mylink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1234,
                CONF_SYSTEM_ID: 456,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "MyLink 1.1.1.1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 1234,
        CONF_SYSTEM_ID: 456,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_import_already_exists(hass):
    """Test we get the form with import source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: 46},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={"any": "data"},
    ), patch(
        "homeassistant.components.somfy_mylink.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.somfy_mylink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1234,
                CONF_SYSTEM_ID: 456,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1234,
                CONF_SYSTEM_ID: 456,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1234,
                CONF_SYSTEM_ID: 456,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_options(hass):
    """Test we can configure reverse."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    import pprint

    pprint.pprint(result)

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={"any": "data"},
    ), patch(
        "homeassistant.components.somfy_mylink.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.somfy_mylink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 1234,
                CONF_SYSTEM_ID: 456,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "MyLink 1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 1234,
        CONF_SYSTEM_ID: 456,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
