"""Test the Kuler Sky config flow."""
import pykulersky

from homeassistant import config_entries, setup
from homeassistant.components.kulersky.config_flow import DOMAIN

from tests.async_mock import MagicMock, patch


async def test_flow_success(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        (
            "homeassistant.components.kulersky.config_flow"
            ".pykulersky.discover_bluetooth_devices"
        ),
        return_value=[
            {"address": "AA:BB:CC:11:22:33", "name": "Bedroom"},
            {"address": "DD:EE:FF:44:55:66", "name": "Living room"},
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert not result["errors"]
    assert result["data_schema"].schema["device"].container == [
        "AA:BB:CC:11:22:33 Bedroom",
        "DD:EE:FF:44:55:66 Living room",
    ]

    light = MagicMock(spec=pykulersky.Light)
    light.address = "AA:BB:CC:11:22:33"
    light.name = "Bedroom"
    light.connected = False
    with patch(
        "homeassistant.components.kulersky.light.pykulersky.Light"
    ) as mockdevice, patch.object(light, "connect"), patch.object(
        light, "get_color", return_value=(0, 0, 0, 0)
    ):
        mockdevice.return_value = light
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"device": "AA:BB:CC:11:22:33 Bedroom"}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "Bedroom"
    assert result["data"] == {
        "address": "AA:BB:CC:11:22:33",
        "name": "Bedroom",
    }


async def test_discovery_error(hass):
    """Test an error in discovery."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        (
            "homeassistant.components.kulersky.config_flow"
            ".pykulersky.discover_bluetooth_devices"
        ),
        side_effect=pykulersky.PykulerskyException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "abort"
    assert result["reason"] == "scan_error"


async def test_connect_error(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        (
            "homeassistant.components.kulersky.config_flow"
            ".pykulersky.discover_bluetooth_devices"
        ),
        return_value=[
            {"address": "AA:BB:CC:11:22:33", "name": "Bedroom"},
            {"address": "DD:EE:FF:44:55:66", "name": "Living room"},
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result["type"] == "form"
    assert not result["errors"]
    assert result["data_schema"].schema["device"].container == [
        "AA:BB:CC:11:22:33 Bedroom",
        "DD:EE:FF:44:55:66 Living room",
    ]

    light = MagicMock(spec=pykulersky.Light)
    light.address = "AA:BB:CC:11:22:33"
    light.name = "Bedroom"
    light.connected = False
    with patch(
        (
            "homeassistant.components.kulersky.config_flow"
            ".pykulersky.discover_bluetooth_devices"
        ),
        return_value=[
            {"address": "AA:BB:CC:11:22:33", "name": "Bedroom"},
            {"address": "DD:EE:FF:44:55:66", "name": "Living room"},
        ],
    ), patch(
        "homeassistant.components.kulersky.light.pykulersky.Light"
    ) as mockdevice, patch.object(
        light, "connect", side_effect=pykulersky.PykulerskyException
    ):
        mockdevice.return_value = light
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"device": "AA:BB:CC:11:22:33 Bedroom"}
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"device": "cannot_connect"}
    assert result["data_schema"].schema["device"].container == [
        "AA:BB:CC:11:22:33 Bedroom",
        "DD:EE:FF:44:55:66 Living room",
    ]
