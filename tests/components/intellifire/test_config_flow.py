"""Test the IntelliFire config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from intellifire4py.exceptions import LoginException

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.intellifire.config_flow import MANUAL_ENTRY_STRING
from homeassistant.components.intellifire.const import CONF_USER_ID, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import mock_api_connection_error

from tests.common import MockConfigEntry


@patch.multiple(
    "homeassistant.components.intellifire.config_flow.IntellifireAPICloud",
    login=AsyncMock(),
    get_user_id=MagicMock(return_value="intellifire"),
    get_fireplace_api_key=MagicMock(return_value="key"),
)
async def test_no_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test we should get the manual discovery form - because no discovered fireplaces."""
    with patch(
        "homeassistant.components.intellifire.config_flow.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual_device_entry"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "api_config"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test", CONF_PASSWORD: "AROONIE"},
    )
    await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Fireplace 12345"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test",
        CONF_PASSWORD: "AROONIE",
        CONF_API_KEY: "key",
        CONF_USER_ID: "intellifire",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@patch.multiple(
    "homeassistant.components.intellifire.config_flow.IntellifireAPICloud",
    login=AsyncMock(side_effect=mock_api_connection_error()),
    get_user_id=MagicMock(return_value="intellifire"),
    get_fireplace_api_key=MagicMock(return_value="key"),
)
async def test_single_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test single fireplace UDP discovery."""
    with patch(
        "homeassistant.components.intellifire.config_flow.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.69"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.69"}
    )
    await hass.async_block_till_done()
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test", CONF_PASSWORD: "AROONIE"},
    )
    await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "iftapi_connect"}


@patch.multiple(
    "homeassistant.components.intellifire.config_flow.IntellifireAPICloud",
    login=AsyncMock(side_effect=LoginException),
    get_user_id=MagicMock(return_value="intellifire"),
    get_fireplace_api_key=MagicMock(return_value="key"),
)
async def test_single_discovery_loign_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test single fireplace UDP discovery."""
    with patch(
        "homeassistant.components.intellifire.config_flow.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.69"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.69"}
    )
    await hass.async_block_till_done()
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test", CONF_PASSWORD: "AROONIE"},
    )
    await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "api_error"}


async def test_manual_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test for multiple Fireplace discovery - involving a pick_device step."""
    with patch(
        "homeassistant.components.intellifire.config_flow.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.69", "192.168.1.33", "192.168.169"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["step_id"] == "pick_device"
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: MANUAL_ENTRY_STRING}
    )

    await hass.async_block_till_done()
    assert result2["step_id"] == "manual_device_entry"


async def test_multi_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test for multiple fireplace discovery - involving a pick_device step."""
    with patch(
        "homeassistant.components.intellifire.config_flow.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.69", "192.168.1.33", "192.168.169"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["step_id"] == "pick_device"
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.33"}
    )
    await hass.async_block_till_done()
    assert result["step_id"] == "pick_device"


async def test_multi_discovery_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test for multiple fireplace discovery - involving a pick_device step."""
    with patch(
        "homeassistant.components.intellifire.config_flow.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.69", "192.168.1.33", "192.168.169"],
    ):
        mock_intellifire_config_flow.poll.side_effect = ConnectionError

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "pick_device"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.33"}
        )
        await hass.async_block_till_done()
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect_manual_entry(
    hass: HomeAssistant,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder_single: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    mock_intellifire_config_flow.poll.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual_device_entry"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_picker_already_discovered(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test single fireplace UDP discovery."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.3",
        },
        title="Fireplace",
        unique_id=44444,
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.intellifire.config_flow.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.3"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.4",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert len(mock_setup_entry.mock_calls) == 0


@patch.multiple(
    "homeassistant.components.intellifire.config_flow.IntellifireAPICloud",
    login=AsyncMock(),
    get_user_id=MagicMock(return_value="intellifire"),
    get_fireplace_api_key=MagicMock(return_value="key"),
)
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test the reauth flow."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.3",
        },
        title="Fireplace 1234",
        version=1,
        unique_id="4444",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reauth",
            "unique_id": entry.unique_id,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "api_config"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test", CONF_PASSWORD: "AROONIE"},
    )
    await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.ABORT
    assert entry.data[CONF_PASSWORD] == "AROONIE"
    assert entry.data[CONF_USERNAME] == "test"


async def test_dhcp_discovery_intellifire_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test successful DHCP Discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
            hostname="zentrios-Test",
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "dhcp_confirm"
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input={}
    )
    assert result3["title"] == "Fireplace 12345"
    assert result3["data"] == {"host": "1.1.1.1"}


async def test_dhcp_discovery_non_intellifire_device(
    hass: HomeAssistant,
    mock_intellifire_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test failed DHCP Discovery."""

    mock_intellifire_config_flow.poll.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
            hostname="zentrios-Evil",
        ),
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_intellifire_device"
