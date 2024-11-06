"""Test fixtures for bang_olufsen."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from mozart_api.models import (
    Action,
    BeolinkPeer,
    BeolinkSelf,
    ContentItem,
    ListeningMode,
    ListeningModeFeatures,
    ListeningModeRef,
    ListeningModeTrigger,
    PlaybackContentMetadata,
    PlaybackProgress,
    PlaybackState,
    PlayQueueSettings,
    ProductState,
    RemoteMenuItem,
    RenderingState,
    SoftwareUpdateState,
    SoftwareUpdateStatus,
    Source,
    SourceArray,
    SourceTypeEnum,
    VolumeState,
)
import pytest

from homeassistant.components.bang_olufsen.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import (
    TEST_DATA_CREATE_ENTRY,
    TEST_DATA_CREATE_ENTRY_2,
    TEST_FRIENDLY_NAME,
    TEST_FRIENDLY_NAME_3,
    TEST_FRIENDLY_NAME_4,
    TEST_HOST_3,
    TEST_HOST_4,
    TEST_JID_1,
    TEST_JID_3,
    TEST_JID_4,
    TEST_NAME,
    TEST_NAME_2,
    TEST_SERIAL_NUMBER,
    TEST_SERIAL_NUMBER_2,
    TEST_SOUND_MODE,
    TEST_SOUND_MODE_2,
    TEST_SOUND_MODE_NAME,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL_NUMBER,
        data=TEST_DATA_CREATE_ENTRY,
        title=TEST_NAME,
    )


@pytest.fixture
def mock_config_entry_2() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SERIAL_NUMBER_2,
        data=TEST_DATA_CREATE_ENTRY_2,
        title=TEST_NAME_2,
    )


@pytest.fixture
async def mock_media_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mozart_client: AsyncMock,
) -> None:
    """Mock media_player entity."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)


@pytest.fixture
def mock_mozart_client() -> Generator[AsyncMock]:
    """Mock MozartClient."""
    with (
        patch(
            "homeassistant.components.bang_olufsen.MozartClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.bang_olufsen.config_flow.MozartClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        # REST API client methods
        client.get_beolink_self = AsyncMock()
        client.get_beolink_self.return_value = BeolinkSelf(
            friendly_name=TEST_FRIENDLY_NAME, jid=TEST_JID_1
        )
        client.get_softwareupdate_status = AsyncMock()
        client.get_softwareupdate_status.return_value = SoftwareUpdateStatus(
            software_version="1.0.0", state=SoftwareUpdateState()
        )
        client.get_product_state = AsyncMock()
        client.get_product_state.return_value = ProductState(
            volume=VolumeState(),
            playback=PlaybackState(
                metadata=PlaybackContentMetadata(),
                progress=PlaybackProgress(),
                source=Source(),
                state=RenderingState(value="started"),
            ),
        )
        client.get_available_sources = AsyncMock()
        client.get_available_sources.return_value = SourceArray(
            items=[
                # Is not playable, so should not be user selectable
                Source(
                    name="AirPlay",
                    id="airPlay",
                    is_enabled=True,
                    is_multiroom_available=False,
                ),
                # The only available beolink source
                Source(
                    name="Tidal",
                    id="tidal",
                    is_enabled=True,
                    is_multiroom_available=True,
                    is_playable=True,
                ),
                Source(
                    name="Line-In",
                    id="lineIn",
                    is_enabled=True,
                    is_multiroom_available=False,
                    is_playable=True,
                ),
                # Is disabled and not playable, so should not be user selectable
                Source(
                    name="Powerlink",
                    id="pl",
                    is_enabled=False,
                ),
            ]
        )
        client.get_remote_menu = AsyncMock()
        client.get_remote_menu.return_value = {
            # Music category, so shouldn't be included in video sources
            "b355888b-2cde-5f94-8592-d47b71d52a27": RemoteMenuItem(
                action_list=[
                    Action(
                        button_name=None,
                        content_id="netRadio://6629967157728971",
                        deezer_user_id=None,
                        gain_db=None,
                        listening_mode_id=None,
                        preset_key=None,
                        queue_item=None,
                        queue_settings=None,
                        radio_station_id=None,
                        source=None,
                        speaker_group_id=None,
                        stand_position=None,
                        stop_duration=None,
                        tone_name=None,
                        type="triggerContent",
                        volume_level=None,
                    )
                ],
                scene_list=None,
                disabled=None,
                dynamic_list=None,
                first_child_menu_item_id=None,
                label="Yle Radio Suomi Helsinki",
                next_sibling_menu_item_id="0b4552f8-7ac6-5046-9d44-5410a815b8d6",
                parent_menu_item_id="eee0c2d0-2b3a-4899-a708-658475c38926",
                available=None,
                content=ContentItem(
                    categories=["music"],
                    content_uri="netRadio://6629967157728971",
                    label="Yle Radio Suomi Helsinki",
                    source=SourceTypeEnum(value="netRadio"),
                ),
                fixed=True,
                id="b355888b-2cde-5f94-8592-d47b71d52a27",
            ),
            # Has "hdmi" as category, so should be included in video sources
            "b6591565-80f4-4356-bcd9-c92ca247f0a9": RemoteMenuItem(
                action_list=[
                    Action(
                        button_name=None,
                        content_id="tv://hdmi_1",
                        deezer_user_id=None,
                        gain_db=None,
                        listening_mode_id=None,
                        preset_key=None,
                        queue_item=None,
                        queue_settings=None,
                        radio_station_id=None,
                        source=None,
                        speaker_group_id=None,
                        stand_position=None,
                        stop_duration=None,
                        tone_name=None,
                        type="triggerContent",
                        volume_level=None,
                    )
                ],
                scene_list=None,
                disabled=False,
                dynamic_list="none",
                first_child_menu_item_id=None,
                label="HDMI A",
                next_sibling_menu_item_id="0ba98974-7b1f-40dc-bc48-fbacbb0f1793",
                parent_menu_item_id="b66c835b-6b98-4400-8f84-6348043792c7",
                available=True,
                content=ContentItem(
                    categories=["hdmi"],
                    content_uri="tv://hdmi_1",
                    label="HDMI A",
                    source=SourceTypeEnum(value="tv"),
                ),
                fixed=False,
                id="b6591565-80f4-4356-bcd9-c92ca247f0a9",
            ),
            # The parent remote menu item. Has the TV label and should therefore not be included in video sources
            "b66c835b-6b98-4400-8f84-6348043792c7": RemoteMenuItem(
                action_list=[],
                scene_list=None,
                disabled=False,
                dynamic_list="none",
                first_child_menu_item_id="b6591565-80f4-4356-bcd9-c92ca247f0a9",
                label="TV",
                next_sibling_menu_item_id="0c4547fe-d3cc-4348-a425-473595b8c9fb",
                parent_menu_item_id=None,
                available=True,
                content=None,
                fixed=True,
                id="b66c835b-6b98-4400-8f84-6348043792c7",
            ),
            # Has an empty content, so should not be included
            "64c9da45-3682-44a4-8030-09ed3ef44160": RemoteMenuItem(
                action_list=[],
                scene_list=None,
                disabled=False,
                dynamic_list="none",
                first_child_menu_item_id=None,
                label="ListeningPosition",
                next_sibling_menu_item_id=None,
                parent_menu_item_id="0c4547fe-d3cc-4348-a425-473595b8c9fb",
                available=True,
                content=None,
                fixed=True,
                id="64c9da45-3682-44a4-8030-09ed3ef44160",
            ),
        }
        client.get_beolink_peers = AsyncMock()
        client.get_beolink_peers.return_value = [
            BeolinkPeer(
                friendly_name=TEST_FRIENDLY_NAME_3,
                jid=TEST_JID_3,
                ip_address=TEST_HOST_3,
            ),
            BeolinkPeer(
                friendly_name=TEST_FRIENDLY_NAME_4,
                jid=TEST_JID_4,
                ip_address=TEST_HOST_4,
            ),
        ]
        client.get_beolink_listeners = AsyncMock()
        client.get_beolink_listeners.return_value = [
            BeolinkPeer(
                friendly_name=TEST_FRIENDLY_NAME_3,
                jid=TEST_JID_3,
                ip_address=TEST_HOST_3,
            ),
            BeolinkPeer(
                friendly_name=TEST_FRIENDLY_NAME_4,
                jid=TEST_JID_4,
                ip_address=TEST_HOST_4,
            ),
        ]

        client.get_listening_mode_set = AsyncMock()
        client.get_listening_mode_set.return_value = [
            ListeningMode(
                id=TEST_SOUND_MODE,
                name=TEST_SOUND_MODE_NAME,
                features=ListeningModeFeatures(),
                triggers=[ListeningModeTrigger()],
            ),
            ListeningMode(
                id=TEST_SOUND_MODE_2,
                name=TEST_SOUND_MODE_NAME,
                features=ListeningModeFeatures(),
                triggers=[ListeningModeTrigger()],
            ),
            ListeningMode(
                id=345,
                name=f"{TEST_SOUND_MODE_NAME} 2",
                features=ListeningModeFeatures(),
                triggers=[ListeningModeTrigger()],
            ),
        ]
        client.get_active_listening_mode = AsyncMock()
        client.get_active_listening_mode.return_value = ListeningModeRef(
            href="",
            id=123,
        )
        client.get_settings_queue = AsyncMock()
        client.get_settings_queue.return_value = PlayQueueSettings(
            repeat="none",
            shuffle=False,
        )

        client.post_standby = AsyncMock()
        client.set_current_volume_level = AsyncMock()
        client.set_volume_mute = AsyncMock()
        client.post_playback_command = AsyncMock()
        client.seek_to_position = AsyncMock()
        client.post_clear_queue = AsyncMock()
        client.post_overlay_play = AsyncMock()
        client.post_uri_source = AsyncMock()
        client.run_provided_scene = AsyncMock()
        client.activate_preset = AsyncMock()
        client.start_deezer_flow = AsyncMock()
        client.add_to_queue = AsyncMock()
        client.post_remote_trigger = AsyncMock()
        client.set_active_source = AsyncMock()
        client.post_beolink_expand = AsyncMock()
        client.join_beolink_peer = AsyncMock()
        client.post_beolink_unexpand = AsyncMock()
        client.post_beolink_leave = AsyncMock()
        client.post_beolink_allstandby = AsyncMock()
        client.join_latest_beolink_experience = AsyncMock()
        client.activate_listening_mode = AsyncMock()
        client.set_settings_queue = AsyncMock()

        # Non-REST API client methods
        client.check_device_connection = AsyncMock()
        client.close_api_client = AsyncMock()

        # WebSocket listener
        client.connect_notifications = AsyncMock()
        client.disconnect_notifications = Mock()
        client.websocket_connected = False

        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock successful setup entry."""
    with patch(
        "homeassistant.components.bang_olufsen.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
