"""Test integration initialization."""
from homeassistant.components.zwave_mqtt import DOMAIN, PLATFORMS, const

from .common import setup_zwave


async def test_init_entry(hass):
    """Test setting up config entry."""
    await setup_zwave(hass, "generic_network_dump.csv")

    # Verify integration + platform loaded.
    assert "zwave_mqtt" in hass.config.components
    for platform in PLATFORMS:
        assert platform in hass.config.components, platform
        assert f"{platform}.{DOMAIN}" in hass.config.components, f"{platform}.{DOMAIN}"

    # Verify services registered
    assert hass.services.has_service(DOMAIN, const.SERVICE_ADD_NODE)
    assert hass.services.has_service(DOMAIN, const.SERVICE_REMOVE_NODE)
    assert hass.services.has_service(DOMAIN, const.SERVICE_REMOVE_FAILED_NODE)
    assert hass.services.has_service(DOMAIN, const.SERVICE_REPLACE_FAILED_NODE)
    assert hass.services.has_service(DOMAIN, const.SERVICE_CANCEL_COMMAND)
    assert hass.services.has_service(DOMAIN, const.SERVICE_SET_CONFIG_PARAMETER)
