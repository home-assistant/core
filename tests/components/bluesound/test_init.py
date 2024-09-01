# async def test_unload_entry(hass: HomeAssistant, config_entry, controller) -> None:
#     """Test entries are unloaded correctly."""
#     controller_manager = Mock(ControllerManager)
#     hass.data[DOMAIN] = {DATA_CONTROLLER_MANAGER: controller_manager}
#     with patch.object(
#         hass.config_entries, "async_forward_entry_unload", return_value=True
#     ) as unload:
#         assert await async_unload_entry(hass, config_entry)
#         await hass.async_block_till_done()
#         assert controller_manager.disconnect.call_count == 1
#         assert unload.call_count == 1
#     assert DOMAIN not in hass.data

from homeassistant.components.bluesound import async_unload_entry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, setup_config_entry: None) -> None:
    """Test a successful setup entry."""
    assert hass.states.get("media_player.player_name").state == "playing"


async def test_unload_entry(
    hass: HomeAssistant, setup_config_entry: None, config_entry: MockConfigEntry
) -> None:
    """Test entries are unloaded correctly."""
    assert await async_unload_entry(hass, config_entry)
    await hass.async_block_till_done()

    assert hass.states.get("media_player.player_name").state == "unavailable" # why? shouldn't it be removed?
