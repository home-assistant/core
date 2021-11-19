"""Test the Tesla Wall Connector config flow."""
from unittest.mock import patch

import tesla_wall_connector

from homeassistant import config_entries, setup
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS, MAC_ADDRESS
from homeassistant.components.tesla_wall_connector.config_flow import CannotConnect
from homeassistant.components.tesla_wall_connector.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    fake_version_obj = tesla_wall_connector.wall_connector.Version(
        {"serial_number": "abc123"}
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=fake_version_obj,
    ), patch(
        "homeassistant.components.tesla_wall_connector.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Tesla Wall Connector"
    assert result2["data"] == {"host": "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(hass):
    """Test we get already configured."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="abc123", data={"host": "0.0.0.0"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    fake_version_obj = tesla_wall_connector.wall_connector.Version(
        {"serial_number": "abc123"}
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=fake_version_obj,
    ), patch(
        "homeassistant.components.tesla_wall_connector.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

        assert result2["type"] == "abort"
        assert result2["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data["host"] == "1.1.1.1"


async def test_dhcp_can_finish(hass):
    """Test DHCP discovery flow can finish right away."""

    fake_version_obj = tesla_wall_connector.wall_connector.Version(
        {
            "serial_number": "abc123",
            "part_number": "part_123",
            "firmware_version": "1.2.3",
        }
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=fake_version_obj,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data={
                HOSTNAME: "teslawallconnector_abc",
                IP_ADDRESS: "1.2.3.4",
                MAC_ADDRESS: "DC:44:27:12:12",
            },
        )
        await hass.async_block_till_done()
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=fake_version_obj,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {"host": "1.2.3.4"}


async def test_dhcp_already_exists(hass):
    """Test DHCP discovery flow when device already exists."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="abc123", data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)

    fake_version_obj = tesla_wall_connector.wall_connector.Version(
        {"serial_number": "abc123"}
    )

    with patch(
        "tesla_wall_connector.WallConnector.async_get_version",
        return_value=fake_version_obj,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data={
                HOSTNAME: "teslawallconnector_aabbcc",
                IP_ADDRESS: "1.2.3.4",
                MAC_ADDRESS: "aa:bb:cc:dd:ee:ff",
            },
        )
        await hass.async_block_till_done()

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"
