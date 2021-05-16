"""Test the Nobø Ecohub config flow."""
from unittest.mock import PropertyMock, patch

from homeassistant import config_entries, setup
from homeassistant.components.nobo_hub.config_flow import CannotConnect
from homeassistant.components.nobo_hub.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_configure_with_ip(hass: HomeAssistant) -> None:
    """Test configuring with IP address."""

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

        with patch("pynobo.nobo.async_connect_hub", return_value=True), patch(
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
        assert len(mock_setup_entry.mock_calls) == 1


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

        with patch("pynobo.nobo.async_connect_hub", return_value=True), patch(
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
                },
            )
            await hass.async_block_till_done()

        assert result2["type"] == "create_entry"
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_configure_device_not_found(hass: HomeAssistant) -> None:
    """Test we handle device not found."""

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

        with patch("pynobo.nobo.async_connect_hub", return_value=True), patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "serial": "223456789012",
                },
            )
            await hass.async_block_till_done()

        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "device_not_found"}


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
            {"serial": "1234567890", "ip_address": "1.1.1.1"},
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
            DOMAIN, context={"source": config_entries.SOURCE_USER}
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
            side_effect=CannotConnect,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"serial": "123456789012", "ip_address": "1.1.1.1"},
            )

        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "cannot_connect"}
