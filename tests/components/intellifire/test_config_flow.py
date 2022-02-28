"""Test the IntelliFire config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.intellifire.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder_single: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace"
    assert result2["data"] == {CONF_HOST: "1.1.1.1"}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_no_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder_none: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace"
    assert result2["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test single firedplace UDP discovery."""
    with patch(
        "intellifire4py.udp.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.69"],
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Fireplace"
        assert result["data"] == {CONF_HOST: "192.168.1.69"}
        assert len(mock_setup_entry.mock_calls) == 1


async def test_mutli_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test for multiple firepalce discovery - involing a pick_device step."""
    with patch(
        "intellifire4py.udp.AsyncUDPFireplaceFinder.search_fireplace",
        return_value=["192.168.1.69", "192.168.1.33", "192.168.169"],
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["step_id"] == "pick_device"
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.33"}
        )
        await hass.async_block_till_done()
        assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result2["title"] == "Fireplace"
        assert result2["data"] == {CONF_HOST: "192.168.1.33"}
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder_single: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    mock_intellifire_config_flow.poll.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}
