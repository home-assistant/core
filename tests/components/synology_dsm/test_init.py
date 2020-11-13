"""Tests for the Synology DSM component."""
from homeassistant.components.synology_dsm import _async_setup_services
from homeassistant.components.synology_dsm.const import DOMAIN, SERVICES
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import HomeAssistantType

from .consts import HOST, PASSWORD, PORT, USE_SSL, USERNAME


async def test_services_registered(hass: HomeAssistantType):
    """Test if all services are registered."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_SSL: USE_SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    await _async_setup_services(hass)
    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)
