"""Tests for the Homematic integration."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.homematic.const import (
    ATTR_ADDRESS,
    ATTR_INTERFACE,
    ATTR_PARAMSET,
    ATTR_PARAMSET_KEY,
    DATA_HOMEMATIC,
    SERVICE_PUT_PARAMSET,
    SERVICE_RECONNECT,
    SERVICE_SET_INSTALL_MODE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component

DOMAIN = "homematic"
BASE_CONFIG = {DOMAIN: {"hosts": {"ccu2": {"host": "127.0.0.1"}}}}


@pytest.fixture
async def setup_homematic(hass: HomeAssistant) -> None:
    """Set up the homematic component."""
    with patch(
        "homeassistant.components.homematic.HMConnection",
        return_value=MagicMock(),
    ):
        await async_setup_component(hass, DOMAIN, BASE_CONFIG)
        await hass.async_block_till_done()


async def test_set_install_mode_admin_allowed(
    hass: HomeAssistant,
    setup_homematic: None,
    hass_admin_user: MockUser,
) -> None:
    """Test that admin users can call set_install_mode."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_INSTALL_MODE,
        {ATTR_INTERFACE: "ccu2"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    hass.data[DATA_HOMEMATIC].setInstallMode.assert_called_once_with(
        "ccu2", t=60, mode=1, address=None
    )


async def test_set_install_mode_non_admin_rejected(
    hass: HomeAssistant,
    setup_homematic: None,
    hass_read_only_user: MockUser,
) -> None:
    """Test that non-admin users cannot call set_install_mode."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_INSTALL_MODE,
            {ATTR_INTERFACE: "ccu2"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )


@pytest.mark.usefixtures("setup_homematic")
async def test_reconnect(hass: HomeAssistant) -> None:
    """Test the reconnect action."""
    await hass.services.async_call(DOMAIN, SERVICE_RECONNECT, blocking=True)
    hass.data[DATA_HOMEMATIC].reconnect.assert_called_once_with()


@pytest.mark.usefixtures("setup_homematic")
async def test_put_paramset(hass: HomeAssistant) -> None:
    """Test the put_paramset action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PUT_PARAMSET,
        {
            ATTR_INTERFACE: "ccu2",
            ATTR_ADDRESS: "abc123",
            ATTR_PARAMSET_KEY: "master",
            ATTR_PARAMSET: {"WEEK_PROGRAM_POINTER": 1},
        },
        blocking=True,
    )
    hass.data[DATA_HOMEMATIC].putParamset.assert_called_once_with(
        "ccu2", "ABC123", "MASTER", {"WEEK_PROGRAM_POINTER": 1}, None
    )
