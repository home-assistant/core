"""Tests for the Homematic integration."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.homematic.const import (
    ATTR_INTERFACE,
    DATA_HOMEMATIC,
    SERVICE_SET_INSTALL_MODE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component

from tests.common import MockUser

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
