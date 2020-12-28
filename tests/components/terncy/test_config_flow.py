"""Test the Terncy config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.terncy.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP,
    CONF_NAME,
    CONF_PORT,
    DOMAIN,
    TERNCY_HUB_SVC_NAME,
)

from tests.async_mock import patch

PATCH_MODULE = "homeassistant.components.terncy"
HUB_DEV_ID = "box-12-34-56-78-90-ab"


def _patch_discovery(no_device=False):
    def _mocked_get_discovered_devices(mgr):
        if no_device:
            return {}
        return {
            HUB_DEV_ID: {
                CONF_NAME: "terncy hub",
                CONF_IP: "192.168.1.100",
                CONF_PORT: 443,
            }
        }

    return patch(
        f"{PATCH_MODULE}._get_discovered_devices",
        side_effect=_mocked_get_discovered_devices,
    )


async def test_user_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    uinput = {
        CONF_DEVICE: HUB_DEV_ID,
    }
    with _patch_discovery():
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=uinput
        )
        assert result2["type"] == "form"
        assert result2["step_id"] == "begin_pairing"


async def test_zeroconf(hass):
    """Test zeroconf."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "name": "box-12-34-56-78-0a-bc." + TERNCY_HUB_SVC_NAME,
            CONF_HOST: "192.168.1.100",
            "properties": {
                CONF_NAME: "terncy hub",
                CONF_IP: "192.168.1.100",
                CONF_PORT: 443,
            },
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
