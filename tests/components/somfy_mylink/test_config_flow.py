"""Test the Somfy MyLink config flow."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import dhcp
from homeassistant.components.somfy_mylink.const import (
    CONF_REVERSED_TARGET_IDS,
    CONF_SYSTEM_ID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={"any": "data"},
    ), patch(
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
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if already configured."""

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
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
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


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
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


async def test_form_unknown_error(hass: HomeAssistant) -> None:
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


async def test_options_not_loaded(hass: HomeAssistant) -> None:
    """Test options will not display until loaded."""

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
        assert result["type"] == data_entry_flow.FlowResultType.ABORT


@pytest.mark.parametrize("reversed", [True, False])
async def test_options_with_targets(hass: HomeAssistant, reversed) -> None:
    """Test we can configure reverse for a target."""

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
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"target_id": "a"},
        )

        assert result2["type"] == data_entry_flow.FlowResultType.FORM
        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"reverse": reversed},
        )

        assert result3["type"] == data_entry_flow.FlowResultType.FORM

        result4 = await hass.config_entries.options.async_configure(
            result3["flow_id"],
            user_input={"target_id": None},
        )
        assert result4["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        assert config_entry.options == {
            CONF_REVERSED_TARGET_IDS: {"a": reversed},
        }

        await hass.async_block_till_done()


async def test_form_user_already_configured_from_dhcp(hass: HomeAssistant) -> None:
    """Test we abort if already configured from dhcp."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: 46},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={"any": "data"},
    ), patch(
        "homeassistant.components.somfy_mylink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="somfy_eeff",
            ),
        )

        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_already_configured_with_ignored(hass: HomeAssistant) -> None:
    """Test ignored entries do not break checking for existing entries."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
            hostname="somfy_eeff",
        ),
    )
    assert result["type"] == "form"


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test we can process the discovery from dhcp."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
            hostname="somfy_eeff",
        ),
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.somfy_mylink.config_flow.SomfyMyLinkSynergy.status_info",
        return_value={"any": "data"},
    ), patch(
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
    assert len(mock_setup_entry.mock_calls) == 1
