"""The tests for the denonavr media player platform."""

from homeassistant.components import media_player
from homeassistant.components.lyngdorf.config_flow import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_NAME = "Test_Receiver"
TEST_MODEL = "model5"
TEST_MAC = "11:22:33:44:55:66"
TEST_DEVICE_ID = "device 123"
TEST_DEVICE_TYPE = "device type"
TEST_SERIALNUMBER = "123456789"
TEST_MANUFACTURER = "Lyngdorf"
TEST_RECEIVER_TYPE = "avr-x"
TEST_ZONE = "Main"
TEST_UNIQUE_ID = f"{TEST_MODEL}-{TEST_SERIALNUMBER}"
TEST_TIMEOUT = 2
TEST_SHOW_ALL_SOURCES = False
TEST_ZONE2 = False
TEST_ZONE3 = False
ENTITY_ID = f"{media_player.DOMAIN}.mock_title"
TEST_SOURCES = ["S 1", "S 2"]
TEST_SOURCE = "S 1"
TEST_SOUND_MODES = ["M 1", "M 2"]
TEST_SOUND_MODE = "M 1"
TEST_VIDEO_INPUT = "VID 1"
TEST_AUDIO_INPUT = "AUD 1"


async def test_options_zone_flow_validation(hass: HomeAssistant) -> None:
    """Mock the etnry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.options.async_init(entry.entry_id)


# async def test_properties(player) -> None:
#     assert player.sound_mode == TEST_SOUND_MODE
#     # assert player.source == TEST_SOURCE
#     assert player.volume_level == -10.0
#     assert not player.should_poll

# ENTRY_MOCK_DATA = {
#     CONF_HOST: "1.1.1.1",
#     CONF_KEYFILE: "",
#     CONF_CERTFILE: "",
#     CONF_CA_CERTS: "",
# }


# async def async_setup_integration(hass, mock_bridge) -> MockConfigEntry:
#     """Set up a mock bridge."""
#     mock_entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_MOCK_DATA)
#     mock_entry.add_to_hass(hass)

#     with patch(
#         "homeassistant.components.lutron_caseta.Smartbridge.create_tls"
#     ) as create_tls:
#         create_tls.return_value = mock_bridge(can_connect=True)
#         await hass.config_entries.async_setup(mock_entry.entry_id)
#         await hass.async_block_till_done()
#     return mock_entry


# @pytest.fixture(name="player")
# def player_fixture(hass, mocker, receiver):
#     """Get standard player."""
#     setup_mock_entities(hass, mocker)

#     player= MP60MainDevice(receiver, config_entry, device_info)
#     player.entity_id = ENTITY_ID
#     player.hass = hass
#     player.platform = MockEntityPlatform(hass)
#     player.async_write_ha_state = Mock()
#     return player


# @pytest.fixture(name="mp60client")
# def mp60client(mocker):
#     patch_mp60client(mocker)
#     return MP60Receiver(TEST_HOST)

# def patch_mp60client(mocker):
#     mocker.patch("lyngdorf.device.MP60Receiver.async_connect", return_value=None)
#     mocker.patch("lyngdorf.device.MP60Receiver.name", return_value=TEST_NAME)
#     mocker.patch("lyngdorf.device.MP60Receiver.volume", return_value=-10.0)
#     mocker.patch("lyngdorf.device.MP60Receiver.zone_b_volume", return_value=-12.0)
#     mocker.patch("lyngdorf.device.MP60Receiver.mute_enabled", return_value=False)
#     mocker.patch("lyngdorf.device.MP60Receiver.zone_b_mute_enabled", return_value=False)
#     # mocker.patch("lyngdorf.device.MP60Receiver.available_sources", return_value=TEST_SOURCES)
#     mocker.patch("lyngdorf.device.MP60Receiver.source", return_value=TEST_SOURCE)
#     # mocker.patch("lyngdorf.device.MP60Receiver.zone_b_available_sources", spec=True,  return_value=['a', 'b', 'c'])
#     mocker.patch("lyngdorf.device.MP60Receiver.zone_b_source", return_value=TEST_SOURCE)
#     # mocker.patch("lyngdorf.device.MP60Receiver.available_sound_modes", return_value=TEST_SOUND_MODES)
#     mocker.patch("lyngdorf.device.MP60Receiver.sound_mode", return_value=TEST_SOUND_MODE)
#     mocker.patch("lyngdorf.device.MP60Receiver.video_input", return_value=TEST_VIDEO_INPUT)
#     mocker.patch("lyngdorf.device.MP60Receiver.audio_input", return_value=TEST_AUDIO_INPUT)
#     mocker.patch("lyngdorf.device.MP60Receiver.power_on", return_value=True)
#     mocker.patch("lyngdorf.device.MP60Receiver.zone_b_power_on", return_value=True)

# async def setup_mock_entities(hass, mocker):
#     """Initialize media_player for tests."""
#     entry_data = {
#         CONF_IP_ADDRESS: TEST_HOST,
#         CONF_DEVICE_ID: TEST_DEVICE_ID,
#         CONF_TYPE: TEST_DEVICE_TYPE,
#         CONF_MAC: TEST_MAC,
#     }

#     mock_entry = MockConfigEntry(
#         domain=DOMAIN,
#         unique_id=TEST_UNIQUE_ID,
#         data=entry_data,
#     )

#     patch_mp60client(mocker)

#     mock_entry.add_to_hass(hass)

#     await hass.config_entries.async_setup(mock_entry.entry_id)
#     await hass.async_block_till_done()

#     mp = hass.states.get(ENTITY_ID)

#     assert mp.state == 'on'
#     assert mp.name == 'Mock Title'
