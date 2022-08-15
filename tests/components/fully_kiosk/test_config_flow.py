"""Test the Fully Kiosk Browser config flow."""
from asynctest import patch
from fullykiosk import FullyKioskError

from homeassistant import config_entries, setup
from homeassistant.components.fully_kiosk.const import DOMAIN

DEVICE_INFO = {
    "deviceName": "Test device",
    "deviceID": "12345",
}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fully_kiosk.config_flow.FullyKiosk.getDeviceInfo",
        return_value=DEVICE_INFO,
    ), patch(
        "homeassistant.components.fully_kiosk.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test device 12345"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.fully_kiosk.config_flow.FullyKiosk.getDeviceInfo",
        side_effect=FullyKioskError(1, "Test error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.fully_kiosk.config_flow.FullyKiosk.getDeviceInfo",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
