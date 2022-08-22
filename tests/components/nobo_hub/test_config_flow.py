"""Test the Nobø Ecohub config flow."""
from unittest.mock import Mock, PropertyMock, patch

from pynobo import nobo

from homeassistant import config_entries, setup
from homeassistant.components.nobo_hub import NoboHubData
from homeassistant.components.nobo_hub.const import (
    CONF_OVERRIDE_TYPE,
    CONF_WEEK_PROFILE_NONE,
    DOMAIN,
)
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_configure_with_discover(hass: HomeAssistant) -> None:
    """Test configure with discover."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["errors"] == {}

    with patch(
        "pynobo.nobo.async_connect_hub", return_value=True
    ) as mock_connect, patch(
        "pynobo.nobo.hub_info",
        new_callable=PropertyMock,
        create=True,
        return_value={"name": "My Nobø Ecohub"},
    ), patch(
        "homeassistant.components.nobo_hub.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device": 0,
                "serial_suffix": "012",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == "create_entry"
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "ip_address": None,
            "serial": "123456789012",
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_show_manual(hass: HomeAssistant) -> None:
    """Test configuration when no hubs are discovered."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["errors"] == {}
        assert result["step_id"] == "manual"


async def test_configure_user_show_manual(hass: HomeAssistant) -> None:
    """Test configuration when user selects manual."""
    await setup.async_setup_component(hass, "persistent_notification", {})

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
                "device": 0,
                "manual": True,
                "serial_suffix": "",
            },
        )
        assert result2["type"] == "form"
        assert result2["errors"] == {}
        assert result2["step_id"] == "manual"


async def test_configure_static_ip_with_discover(hass: HomeAssistant) -> None:
    """Test configure with discover."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["errors"] == {}

    with patch(
        "pynobo.nobo.async_connect_hub", return_value=True
    ) as mock_connect, patch(
        "pynobo.nobo.hub_info",
        new_callable=PropertyMock,
        create=True,
        return_value={"name": "My Nobø Ecohub"},
    ), patch(
        "homeassistant.components.nobo_hub.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "device": 0,
                "serial_suffix": "012",
                "store_ip": True,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == "create_entry"
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {"serial": "123456789012", "ip_address": "1.1.1.1"}
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_manual(hass: HomeAssistant) -> None:
    """Test manual configuration with IP address and full serial number."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}
        )
        assert result["type"] == "form"
        assert result["errors"] == {}

    with patch(
        "pynobo.nobo.async_connect_hub", return_value=True
    ) as mock_connect, patch(
        "pynobo.nobo.hub_info",
        new_callable=PropertyMock,
        create=True,
        return_value={"name": "My Nobø Ecohub"},
    ), patch(
        "homeassistant.components.nobo_hub.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "serial": "123456789012",
                "ip_address": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == "create_entry"
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
            "ip_address": "1.1.1.1",
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_invalid_serial(hass: HomeAssistant) -> None:
    """Test we handle invalid serial error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": 0, "serial_suffix": "ABC"},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_serial"}


async def test_configure_missing_serial_suffix(hass: HomeAssistant) -> None:
    """Test we handle missing serial suffix when configuring discovered hub."""
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
            "device": 0,
            "serial_suffix": "",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "missing_serial_suffix"}


async def test_configure_invalid_serial_manual(hass: HomeAssistant) -> None:
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

    assert result2["type"] == "form"
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

    assert result2["type"] == "form"
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

    with patch(
        "pynobo.nobo.async_connect_hub",
        return_value=False,
    ) as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"device": 0, "serial_suffix": "012"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
    mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test the options flow."""
    zones = {
        "1": {"zone_id": "1", "name": "Kitchen"},
        "2": {"zone_id": "2", "name": "Bedrooms"},
    }
    week_profiles = {
        "1": {"week_profile_id": "1", "name": "Off"},
        "2": {"week_profile_id": "2", "name": "Kitchen On"},
        "3": {"week_profile_id": "3", "name": "Bedrooms On"},
    }
    hub = Mock(nobo)
    type(hub).zones = PropertyMock(return_value=zones)
    type(hub).week_profiles = PropertyMock(return_value=week_profiles)
    entry = MockConfigEntry(
        domain="nobo_hub",
        unique_id="123456789012",
        data={"serial": "123456789012"},
    )
    hass.data[DOMAIN] = {
        entry.entry_id: NoboHubData(hub, lambda remove_listener: remove_listener)
    }
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["description_placeholders"]["zones"] == "1: Kitchen\r2: Bedrooms\r"
    schema = result["data_schema"].schema
    profiles = {CONF_WEEK_PROFILE_NONE, "Off", "Kitchen On", "Bedrooms On"}
    assert set(schema[CONF_COMMAND_OFF].schema.container) == profiles
    assert set(schema[CONF_COMMAND_ON + "_zone_1"].schema.container) == profiles
    assert set(schema[CONF_COMMAND_ON + "_zone_2"].schema.container) == profiles

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "Constant",
            CONF_COMMAND_OFF: "Off",
            CONF_COMMAND_ON + "_zone_1": "Kitchen On",
            CONF_COMMAND_ON + "_zone_2": "Bedrooms On",
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_OVERRIDE_TYPE] == "Constant"
    assert result["data"][CONF_COMMAND_OFF] == "Off"
    assert result["data"][CONF_COMMAND_ON] == {
        "Kitchen": "Kitchen On",
        "Bedrooms": "Bedrooms On",
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "Now",
            CONF_COMMAND_OFF: CONF_WEEK_PROFILE_NONE,
            CONF_COMMAND_ON + "_zone_1": CONF_WEEK_PROFILE_NONE,
            CONF_COMMAND_ON + "_zone_2": CONF_WEEK_PROFILE_NONE,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_OVERRIDE_TYPE] == "Now"
    assert result["data"][CONF_COMMAND_OFF] is None
    assert result["data"][CONF_COMMAND_ON] == {
        "Kitchen": None,
        "Bedrooms": None,
    }
