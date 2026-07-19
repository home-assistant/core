"""Test the Somfy MyLink config flow."""

from unittest.mock import MagicMock

from pysomfymylink import SomfyMyLinkApiError, SomfyMyLinkConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.somfy_mylink.const import (
    CONF_REVERSED_TARGET_IDS,
    CONF_SYSTEM_ID,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 1234,
    CONF_SYSTEM_ID: "456",
}

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="1.1.1.1",
    macaddress="aabbccddeeff",
    hostname="somfy_eeff",
)


async def test_form_user(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "MyLink 1.1.1.1"
    assert result2["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_already_configured(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test we abort if already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: "46"},
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_somfy_mylink.status_info.side_effect = SomfyMyLinkApiError(
        "Invalid auth", code=-32652
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_auth_empty_result(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock
) -> None:
    """Test an empty cover list is treated as invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_somfy_mylink.status_info.return_value = []
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_somfy_mylink.status_info.side_effect = SomfyMyLinkConnectionError(
        "unreachable"
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock
) -> None:
    """Test we handle broad exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_somfy_mylink.status_info.side_effect = ValueError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_not_loaded(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock
) -> None:
    """Test options will not display until loaded."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: "46"},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.parametrize("reversed_", [True, False])
async def test_options_with_targets(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock, reversed_: bool
) -> None:
    """Test we can configure reverse for a target."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: "46"},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"target_id": "CE1A2B3C.1"},
    )
    assert result2["type"] is FlowResultType.FORM

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"reverse": reversed_},
    )
    assert result3["type"] is FlowResultType.FORM

    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={"target_id": None},
    )
    assert result4["type"] is FlowResultType.CREATE_ENTRY

    assert config_entry.options == {
        CONF_REVERSED_TARGET_IDS: {"CE1A2B3C.1": reversed_},
    }
    await hass.async_block_till_done()


async def test_options_unknown_target_raises(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock
) -> None:
    """Test the target_config step raises KeyError for an unknown target."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: "46"},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]

    with pytest.raises(KeyError):
        await flow.async_step_target_config(target_id="does-not-exist")


async def test_form_user_already_configured_from_dhcp(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test we abort if already configured from dhcp."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 12, CONF_SYSTEM_ID: "46"},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
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
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM


async def test_dhcp_discovery(
    hass: HomeAssistant, mock_somfy_mylink: MagicMock, mock_setup_entry: MagicMock
) -> None:
    """Test we can process the discovery from dhcp."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "MyLink 1.1.1.1"
    assert result2["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1
