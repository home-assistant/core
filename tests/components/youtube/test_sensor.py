"""Sensor tests for the YouTube integration."""
from datetime import timedelta
from unittest.mock import patch

from google.auth.exceptions import RefreshError

from homeassistant import config_entries
from homeassistant.components.youtube import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ...common import async_fire_time_changed
from .conftest import TOKEN, ComponentSetup


async def test_sensor(hass: HomeAssistant, setup_integration: ComponentSetup) -> None:
    """Test sensor."""
    await setup_integration()

    state = hass.states.get("sensor.google_for_developers_latest_upload")
    assert state
    assert state.name == "Google for Developers Latest upload"
    assert state.state == "What's new in Google Home in less than 1 minute"
    assert (
        state.attributes["entity_picture"]
        == "https://i.ytimg.com/vi/wysukDrMdqU/sddefault.jpg"
    )

    state = hass.states.get("sensor.google_for_developers_subscribers")
    assert state
    assert state.name == "Google for Developers Subscribers"
    assert state.state == "2290000"
    assert (
        state.attributes["entity_picture"]
        == "https://yt3.ggpht.com/fca_HuJ99xUxflWdex0XViC3NfctBFreIl8y4i9z411asnGTWY-Ql3MeH_ybA4kNaOjY7kyA=s800-c-k-c0x00ffffff-no-rj"
    )


async def test_sensor_reauth_trigger(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test reauth is triggered after a refresh error."""
    await setup_integration()

    with patch(TOKEN, side_effect=RefreshError):
        future = dt_util.utcnow() + timedelta(minutes=15)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()

    assert len(flows) == 1
    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH
