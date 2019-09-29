"""Tests for HomematicIP Cloud HAP."""
import logging

import pytest

from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN,
    HMIPC_HAPID,
)

_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_hmip_ap(hass, fake_hmip_hap, fake_hmip_config_entry):
    """Test Homematicip Access Point setuo."""
    home = hass.data[HMIPC_DOMAIN][fake_hmip_config_entry.data[HMIPC_HAPID]].home
    assert fake_hmip_hap.home is home
    assert len(fake_hmip_hap.home.devices) == 60
