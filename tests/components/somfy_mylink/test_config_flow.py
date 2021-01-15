"""Test the Somfy MyLink config flow."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS, MAC_ADDRESS
from homeassistant.components.somfy_mylink.const import (
    CONF_DEFAULT_REVERSE,
    CONF_ENTITY_CONFIG,
    CONF_REVERSE,
    CONF_REVERSED_TARGET_IDS,
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
                CONF_SYSTEM_ID: "456",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "MyLink 1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 1234,
        CONF_SYSTEM_ID: "456",
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
                CONF_SYSTEM_ID: "456",
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
                CONF_SYSTEM_ID: "456",
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
                CONF_SYSTEM_ID: "456",
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
                CONF_SYSTEM_ID: "456",
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
                CONF_SYSTEM_ID: "456",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_options_not_loaded(hass):
    """Test options will not display until loaded."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: "46"},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.somfy_mylink.SomfyMyLinkSynergy.status_info",
        return_value={"result": []},
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


@pytest.mark.parametrize("reversed", [True, False])
async def test_options_with_targets(hass, reversed):
    """Test we can configure reverse for a target."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: "46"},
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
            user_input={"target_id": "a"},
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"reverse": reversed},
        )

        assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM

        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"],
            user_input={"target_id": None},
        )
        assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        assert config_entry.options == {
            CONF_REVERSED_TARGET_IDS: {"a": reversed},
        }

        await hass.async_block_till_done()


@pytest.mark.parametrize("reversed", [True, False])
async def test_form_import_with_entity_config_modify_options(hass, reversed):
    """Test we can import entity config and modify options."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_imported_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 1234,
            CONF_SYSTEM_ID: "456",
            CONF_DEFAULT_REVERSE: True,
            CONF_ENTITY_CONFIG: {"cover.xyz": {CONF_REVERSE: False}},
        },
    )
    mock_imported_config_entry.add_to_hass(hass)

    mock_status_info = {
        "result": [
            {"targetID": "1.1", "name": "xyz"},
            {"targetID": "1.2", "name": "zulu"},
        ]
    }

    with patch(
        "homeassistant.components.somfy_mylink.SomfyMyLinkSynergy.status_info",
        return_value=mock_status_info,
    ):
        assert await hass.config_entries.async_setup(
            mock_imported_config_entry.entry_id
        )
        await hass.async_block_till_done()

        assert mock_imported_config_entry.options == {
            "reversed_target_ids": {"1.2": True}
        }

        result = await hass.config_entries.options.async_init(
            mock_imported_config_entry.entry_id
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"target_id": "1.2"},
        )

        assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"reverse": reversed},
        )

        assert result3["type"] == data_entry_flow.RESULT_TYPE_FORM

        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"],
            user_input={"target_id": None},
        )
        assert result4["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        # Will not be altered if nothing changes
        assert mock_imported_config_entry.options == {
            CONF_REVERSED_TARGET_IDS: {"1.2": reversed},
        }

        await hass.async_block_till_done()


async def test_form_user_already_configured_from_dhcp(hass):
    """Test we abort if already configured from dhcp."""
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
            context={"source": config_entries.SOURCE_DHCP},
            data={
                IP_ADDRESS: "1.1.1.1",
                MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
                HOSTNAME: "somfy_eeff",
            },
        )

        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_already_configured_with_ignored(hass):
    """Test ignored entries do not break checking for existing entries."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={}, source="ignore")
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data={
            IP_ADDRESS: "1.1.1.1",
            MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
            HOSTNAME: "somfy_eeff",
        },
    )
    assert result["type"] == "form"


async def test_dhcp_discovery(hass):
    """Test we can process the discovery from dhcp."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data={
            IP_ADDRESS: "1.1.1.1",
            MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
            HOSTNAME: "somfy_eeff",
        },
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
                CONF_SYSTEM_ID: "456",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "MyLink 1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 1234,
        CONF_SYSTEM_ID: "456",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
