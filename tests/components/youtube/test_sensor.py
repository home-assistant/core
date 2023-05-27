"""Sensor tests for the YouTube integration."""


from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup


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
