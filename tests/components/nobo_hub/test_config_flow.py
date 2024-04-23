"""Test the Nobø Ecohub config flow."""

from unittest.mock import PropertyMock, patch

from homeassistant import config_entries
from homeassistant.components.nobo_hub.const import CONF_OVERRIDE_TYPE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_configure_with_discover(hass: HomeAssistant) -> None:
    """Test configure with discover."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {}
    assert result2["step_id"] == "selected"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
        patch(
            "homeassistant.components.nobo_hub.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "serial_suffix": "012",
            },
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "My Nobø Ecohub"
        assert result3["data"] == {
            "ip_address": "1.1.1.1",
            "serial": "123456789012",
            "auto_discovered": True,
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_manual(hass: HomeAssistant) -> None:
    """Test manual configuration when no hubs are discovered."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "manual"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
        patch(
            "homeassistant.components.nobo_hub.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "serial": "123456789012",
                "ip_address": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
            "ip_address": "1.1.1.1",
            "auto_discovered": False,
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_user_selected_manual(hass: HomeAssistant) -> None:
    """Test configuration when user selects manual."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "manual",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {}
    assert result2["step_id"] == "manual"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
        patch(
            "homeassistant.components.nobo_hub.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "serial": "123456789012",
                "ip_address": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
            "ip_address": "1.1.1.1",
            "auto_discovered": False,
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_invalid_serial_suffix(hass: HomeAssistant) -> None:
    """Test we handle invalid serial suffix error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"serial_suffix": "ABC"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_serial"}


async def test_configure_invalid_serial_undiscovered(hass: HomeAssistant) -> None:
    """Test we handle invalid serial error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "1.1.1.1", "serial": "123456789"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_serial"}


async def test_configure_invalid_ip_address(hass: HomeAssistant) -> None:
    """Test we handle invalid ip address error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"serial": "123456789012", "ip_address": "ABCD"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ip"}


async def test_configure_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )

    with patch(
        "pynobo.nobo.async_connect_hub",
        return_value=False,
    ) as mock_connect:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"serial_suffix": "012"},
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "cannot_connect"}
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow."""
    config_entry = MockConfigEntry(
        domain="nobo_hub",
        unique_id="123456789012",
        data={"serial": "123456789012", "ip_address": "1.1.1.1", "auto_discover": True},
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.nobo_hub.async_setup_entry", return_value=True
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "Constant",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_OVERRIDE_TYPE: "Constant"}

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "Now",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_OVERRIDE_TYPE: "Now"}
