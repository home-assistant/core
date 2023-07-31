"""Test the Pentair ScreenLogic config flow."""
from unittest.mock import patch

from screenlogicpy import ScreenLogicError
from screenlogicpy.const import (
    SL_GATEWAY_IP,
    SL_GATEWAY_NAME,
    SL_GATEWAY_PORT,
    SL_GATEWAY_SUBTYPE,
    SL_GATEWAY_TYPE,
)

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.screenlogic.config_flow import (
    GATEWAY_MANUAL_ENTRY,
    GATEWAY_SELECT_KEY,
)
from homeassistant.components.screenlogic.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_flow_discovery(hass: HomeAssistant) -> None:
    """Test the flow works with basic discovery."""

    with patch(
        "homeassistant.components.screenlogic.config_flow.discovery.async_discover",
        return_value=[
            {
                SL_GATEWAY_IP: "1.1.1.1",
                SL_GATEWAY_PORT: 80,
                SL_GATEWAY_TYPE: 12,
                SL_GATEWAY_SUBTYPE: 2,
                SL_GATEWAY_NAME: "Pentair: 01-01-01",
            },
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "gateway_select"

    with patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={GATEWAY_SELECT_KEY: "00:c0:33:01:01:01"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Pentair: 01-01-01"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_PORT: 80,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_discover_none(hass: HomeAssistant) -> None:
    """Test when nothing is discovered."""

    with patch(
        "homeassistant.components.screenlogic.config_flow.discovery.async_discover",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "gateway_entry"


async def test_flow_discover_error(hass: HomeAssistant) -> None:
    """Test when discovery errors."""

    with patch(
        "homeassistant.components.screenlogic.config_flow.discovery.async_discover",
        side_effect=ScreenLogicError("Fake error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "gateway_entry"

    with patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.screenlogic.config_flow.login.async_get_mac_address",
        return_value="00-C0-33-01-01-01",
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_PORT: 80,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "Pentair: 01-01-01"
    assert result3["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_PORT: 80,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            hostname="Pentair: 01-01-01",
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
        ),
    )

    assert result["type"] == "form"
    assert result["step_id"] == "gateway_entry"

    with patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.screenlogic.config_flow.login.async_get_mac_address",
        return_value="00-C0-33-01-01-01",
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_PORT: 80,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "Pentair: 01-01-01"
    assert result3["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_PORT: 80,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_manual_entry(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.screenlogic.config_flow.discovery.async_discover",
        return_value=[
            {
                SL_GATEWAY_IP: "1.1.1.1",
                SL_GATEWAY_PORT: 80,
                SL_GATEWAY_TYPE: 12,
                SL_GATEWAY_SUBTYPE: 2,
                SL_GATEWAY_NAME: "Pentair: 01-01-01",
            },
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "gateway_select"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={GATEWAY_SELECT_KEY: GATEWAY_MANUAL_ENTRY}
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {}
    assert result2["step_id"] == "gateway_entry"

    with patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.screenlogic.config_flow.login.async_get_mac_address",
        return_value="00-C0-33-01-01-01",
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_PORT: 80,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "Pentair: 01-01-01"
    assert result3["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_PORT: 80,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.screenlogic.config_flow.discovery.async_discover",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    with patch(
        "homeassistant.components.screenlogic.config_flow.login.async_get_mac_address",
        side_effect=ScreenLogicError("Failed to connect to host at 1.1.1.1:80"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
                CONF_PORT: 80,
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}


async def test_option_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 15},
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {CONF_SCAN_INTERVAL: 15}


async def test_option_flow_defaults(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    }


async def test_option_flow_input_floor(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.screenlogic.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SCAN_INTERVAL: 1}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_SCAN_INTERVAL: MIN_SCAN_INTERVAL,
    }
