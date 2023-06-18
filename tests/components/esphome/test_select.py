"""Test ESPHome selects."""


from homeassistant.core import HomeAssistant


async def test_pipeline_selector(
    hass: HomeAssistant,
    mock_voice_assistant_v1_entry,
) -> None:
    """Test assist pipeline selector."""

    state = hass.states.get("select.test_assist_pipeline")
    assert state is not None
    assert state.state == "preferred"
