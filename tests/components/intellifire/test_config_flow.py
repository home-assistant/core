"""Test the IntelliFire config flow."""
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.intellifire.config_flow import MANUAL_ENTRY_STRING
from homeassistant.components.intellifire.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


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
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual_device_entry"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace 12345"
    assert result2["data"] == {CONF_HOST: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.69"}
    )
    await hass.async_block_till_done()
    print("Result:", result)

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace 12345"
    assert result2["data"] == {CONF_HOST: "192.168.1.69"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
) -> None:
    """Test for multiple firepalce discovery - involing a pick_device step."""
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.168.1.33"}
    )
    await hass.async_block_till_done()
    assert result["step_id"] == "pick_device"

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY


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
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "pick_device"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.33"}
        )
        await hass.async_block_till_done()
        assert result2["type"] == RESULT_TYPE_FORM
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
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_device_entry"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
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
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace 12345"
    assert result2["data"] == {CONF_HOST: "192.168.1.4"}
    assert len(mock_setup_entry.mock_calls) == 2
