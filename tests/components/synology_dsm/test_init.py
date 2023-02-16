"""Tests for the Synology DSM component."""
from unittest.mock import MagicMock, patch

from synology_dsm.exceptions import SynologyDSMLoginInvalidException

from homeassistant import data_entry_flow
from homeassistant.components.synology_dsm.const import DOMAIN, SERVICES
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .consts import HOST, MACS, PASSWORD, PORT, USE_SSL, USERNAME

from tests.common import MockConfigEntry


async def test_services_registered(hass: HomeAssistant, mock_dsm: MagicMock) -> None:
    """Test if all services are registered."""
    with patch(
        "homeassistant.components.synology_dsm.common.SynologyDSM",
        return_value=mock_dsm,
    ), patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        for service in SERVICES:
            assert hass.services.has_service(DOMAIN, service)


async def test_reauth_triggered(hass: HomeAssistant) -> None:
    """Test if reauthentication flow is triggered."""
    with patch(
        "homeassistant.components.synology_dsm.SynoApi.async_setup",
        side_effect=SynologyDSMLoginInvalidException(USERNAME),
    ), patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSMFlowHandler.async_step_reauth",
        return_value={"type": data_entry_flow.FlowResultType.FORM},
    ) as mock_async_step_reauth:
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
        )
        entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        mock_async_step_reauth.assert_called_once()
