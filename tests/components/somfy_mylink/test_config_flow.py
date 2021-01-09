"""Test the Somfy MyLink config flow."""
import asyncio
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.somfy_mylink.const import (
    CONF_DEFAULT_REVERSE,
    CONF_ENTITY_CONFIG,
    CONF_REVERSE,
    CONF_SYSTEM_ID,
    DOMAIN,
)
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


async def test_form_user_already_configured(hass):
    """Test we abort if already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: 46},
    )
    config_entry.add_to_hass(hass)
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

    assert result2["type"] == "abort"
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


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


async def test_form_import_with_entity_config(hass):
    """Test we can import entity config."""
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
                CONF_DEFAULT_REVERSE: True,
                CONF_ENTITY_CONFIG: {"cover.xyz": {CONF_REVERSE: False}},
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "MyLink 1.1.1.1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 1234,
        CONF_SYSTEM_ID: 456,
        CONF_DEFAULT_REVERSE: True,
        CONF_ENTITY_CONFIG: {"cover.xyz": {CONF_REVERSE: False}},
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
        return_value={
            "jsonrpc": "2.0",
            "error": {"code": -32652, "message": "Invalid auth"},
            "id": 818,
        },
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


async def test_form_unknown_error(hass):
    """Test we handle broad exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        side_effect=ValueError,
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
    assert result2["errors"] == {"base": "unknown"}


async def test_options_not_loaded(hass):
    """Test options will not display until loaded."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: 46},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.somfy_mylink.SomfyMyLinkSynergy.status_info",
        return_value={"result": []},
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_options_no_entities(hass):
    """Test we can configure default reverse."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: 46},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.somfy_mylink.SomfyMyLinkSynergy.status_info",
        return_value={"result": []},
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"default_reverse": True},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {
            "default_reverse": True,
        }

        await hass.async_block_till_done()


async def test_options_with_entities(hass):
    """Test we can configure reverse for an entity."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: 46},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.somfy_mylink.SomfyMyLinkSynergy.status_info",
        return_value={
            "result": [
                {
                    "targetID": "a",
                    "name": "Master Window",
                    "type": 0,
                }
            ]
        },
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"default_reverse": True, "entity_id": "cover.master_window"},
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"reverse": False},
        )

        assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM

        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"],
            user_input={"default_reverse": True, "entity_id": None},
        )
        assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        assert config_entry.options == {
            "default_reverse": True,
            "entity_config": {"cover.master_window": {"reverse": False}},
            "entity_config_version": 1,
        }

        await hass.async_block_till_done()
