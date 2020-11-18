"""Helper class to implement include/exclude of entities and domains."""
import fnmatch
import re
from typing import Callable, Dict, List, Pattern

import voluptuous as vol

from homeassistant.const import CONF_DOMAINS, CONF_ENTITIES, CONF_EXCLUDE, CONF_INCLUDE
from homeassistant.core import split_entity_id
from homeassistant.helpers import config_validation as cv

CONF_INCLUDE_DOMAINS = "include_domains"
CONF_INCLUDE_ENTITY_GLOBS = "include_entity_globs"
CONF_INCLUDE_ENTITIES = "include_entities"
CONF_EXCLUDE_DOMAINS = "exclude_domains"
CONF_EXCLUDE_ENTITY_GLOBS = "exclude_entity_globs"
CONF_EXCLUDE_ENTITIES = "exclude_entities"

CONF_ENTITY_GLOBS = "entity_globs"


def convert_filter(config: Dict[str, List[str]]) -> Callable[[str], bool]:
    """Convert the filter schema into a filter."""
    filt = generate_filter(
        config[CONF_INCLUDE_DOMAINS],
        config[CONF_INCLUDE_ENTITIES],
        config[CONF_EXCLUDE_DOMAINS],
        config[CONF_EXCLUDE_ENTITIES],
        config[CONF_INCLUDE_ENTITY_GLOBS],
        config[CONF_EXCLUDE_ENTITY_GLOBS],
    )
    setattr(filt, "config", config)
    setattr(filt, "empty_filter", sum(len(val) for val in config.values()) == 0)
    return filt


BASE_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EXCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_EXCLUDE_ENTITIES, default=[]): cv.entity_ids,
        vol.Optional(CONF_INCLUDE_DOMAINS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_INCLUDE_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_INCLUDE_ENTITIES, default=[]): cv.entity_ids,
    }
)

FILTER_SCHEMA = vol.All(BASE_FILTER_SCHEMA, convert_filter)


def convert_include_exclude_filter(
    config: Dict[str, Dict[str, List[str]]]
) -> Callable[[str], bool]:
    """Convert the include exclude filter schema into a filter."""
    include = config[CONF_INCLUDE]
    # exclude = config[CONF_EXCLUDE]
    exclude = {
        "domains": [
            "ais_ai_service",
            "ais_amplifier_service",
            "ais_audiobooks_service",
            "ais_bookmarks",
            "ais_cloud",
            "ais_device_search_mqtt",
            "ais_dom",
            "ais_dom_device",
            "ais_drives_service",
            "ais_exo_player",
            "ais_files",
            "ais_google_home",
            "ais_help",
            "ais_host",
            "ais_ingress",
            "ais_knowledge_service",
            "ais_mdns",
            "ais_shell_command",
            "ais_spotify_service",
            "ais_updater",
            "ais_usb",
            "ais_wifi_service",
            "ais_yt_service",
            "media_player",
            "group",
        ],
        "entities": [
            "sun.sun",
            "sensor.date",
            "sensor.time",
            "automation.ais_ask_the_question",
            "automation.ais_asystent_domowy_witamy",
            "automation.ais_change_audio_to_mono",
            "automation.ais_change_equalizer_mode",
            "automation.ais_change_player_speed",
            "automation.ais_change_remote_web_access",
            "automation.ais_check_wifi_connection",
            "automation.ais_discovery_info_to_dom_devices",
            "automation.ais_execute_process_command_web_hook",
            "automation.ais_flush_logs",
            "automation.ais_get_books",
            "automation.ais_get_podcast_names",
            "automation.ais_get_radio_names",
            "automation.ais_get_rss_help_items_for_selected_topic",
            "automation.ais_get_rss_news_channels",
            "automation.ais_get_rss_news_items",
            "automation.ais_ifttt_info",
            "automation.ais_search_spotify_tracks",
            "automation.ais_search_youtube_tracks",
            "automation.ais_select_bookmark_to_play",
            "automation.ais_select_device_to_add",
            "automation.ais_set_wifi_config_for_devices",
            "binary_sensor.ais_remote_button",
            "group.ais_add_iot_device",
            "group.ais_bookmarks",
            "group.ais_favorites",
            "group.ais_pogoda",
            "group.ais_rss_help_remote",
            "group.ais_rss_news_remote",
            "group.ais_tts_configuration",
            "group.all_ais_automations",
            "group.all_ais_cameras",
            "group.all_ais_climates",
            "group.all_ais_covers",
            "group.all_ais_devices",
            "group.all_ais_fans",
            "group.all_ais_lights",
            "group.all_ais_locks",
            "group.all_ais_persons",
            "group.all_ais_scenes",
            "group.all_ais_sensors",
            "group.all_ais_switches",
            "group.all_ais_vacuums",
            "input_boolean.ais_audio_mono",
            "input_boolean.ais_auto_update",
            "input_boolean.ais_quiet_mode",
            "input_boolean.ais_remote_access",
            "input_datetime.ais_quiet_mode_start",
            "input_datetime.ais_quiet_mode_stop",
            "input_select.ais_android_wifi_network",
            "input_select.ais_iot_devices_in_network",
            "input_select.ais_music_service",
            "input_select.ais_rss_help_topic",
            "input_select.ais_system_logs_level",
            "input_select.ais_usb_flash_drives",
            "input_text.ais_android_wifi_password",
            "input_text.ais_iot_device_name",
            "input_text.ais_iot_device_wifi_password",
            "input_text.ais_knowledge_query",
            "input_text.ais_music_query",
            "input_text.ais_spotify_query",
            "script.ais_add_item_to_bookmarks",
            "script.ais_add_item_to_favorites",
            "script.ais_button_click",
            "script.ais_cloud_sync",
            "script.ais_connect_android_wifi_network",
            "script.ais_connect_iot_device_to_network",
            "script.ais_restart_system",
            "script.ais_scan_android_wifi_network",
            "script.ais_scan_iot_devices_in_network",
            "script.ais_scan_network_devices",
            "script.ais_stop_system",
            "script.ais_update_system",
            "sensor.ais_all_files",
            "sensor.ais_connect_iot_device_info",
            "sensor.ais_db_connection_info",
            "sensor.ais_dom_mqtt_rf_sensor",
            "sensor.ais_drives",
            "sensor.ais_gallery_img",
            "sensor.ais_logs_settings_info",
            "sensor.ais_player_mode",
            "sensor.ais_secure_android_id_dom",
            "sensor.ais_wifi_service_current_network_info",
            "sensor.aisbackupinfo",
            "sensor.aisbookmarkslist",
            "sensor.aisfavoriteslist",
            "sensor.aisknowledgeanswer",
            "sensor.aisrsshelptext",
            "timer.ais_dom_pin",
            "input_select.book_autor",
            "group.audiobooks_player",
            "input_select.podcast_type",
            "input_select.radio_type",
            "sensor.daytodisplay",
            "group.day_info",
            "group.local_audio",
            "group.radio_player",
            "group.podcast_player",
            "group.music_player",
            "group.internet_status",
            "group.audio_player",
            "group.dom_system_version",
            "sensor.radiolist",
            "sensor.podcastnamelist",
            "sensor.youtubelist",
            "sensor.spotifysearchlist",
            "sensor.spotifylist",
            "sensor.rssnewslist",
            "input_select.rss_news_category",
            "input_select.rss_news_channel",
            "sensor.selected_entity",
            "sensor.wersja_kordynatora",
            "sensor.status_serwisu_zigbee2mqtt",
            "sensor.gate_pairing_pin",
            "persistent_notification.config_entry_discovery",
            "sensor.audiobookschapterslist",
            "automation.zigbee_tryb_parowania",
            "automation.zigbee_wylaczenie_trybu_parowania",
            "input_number.assistant_rate",
            "input_number.media_player_speed",
            "timer.ais_dom_pin_join",
            "media_player.wbudowany_glosnik",
            "input_number.assistant_tone",
            "timer.zigbee_permit_join",
            "input_select.book_name",
            "sensor.podcastlist",
            "sensor.audiobookslist",
            "sensor.rssnewstext",
            "switch.zigbee_tryb_parowania",
            "input_select.book_chapter",
            "input_select.assistant_voice",
            "sensor.network_devices_info_value",
            "input_text.zigbee2mqtt_old_name",
            "input_text.zigbee2mqtt_new_name",
            "sensor.zigbee2mqtt_networkmap",
            "input_text.zigbee2mqtt_remove",
            "input_select.media_player_sound_mode",
            "binary_sensor.updater",
            "weather.dom",
            "binary_sensor.selected_entity",
        ],
        "entity_globs": [],
    }
    filt = convert_filter(
        {
            CONF_INCLUDE_DOMAINS: include[CONF_DOMAINS],
            CONF_INCLUDE_ENTITY_GLOBS: include[CONF_ENTITY_GLOBS],
            CONF_INCLUDE_ENTITIES: include[CONF_ENTITIES],
            CONF_EXCLUDE_DOMAINS: exclude[CONF_DOMAINS],
            CONF_EXCLUDE_ENTITY_GLOBS: exclude[CONF_ENTITY_GLOBS],
            CONF_EXCLUDE_ENTITIES: exclude[CONF_ENTITIES],
        }
    )
    setattr(filt, "config", config)
    return filt


INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER = vol.Schema(
    {
        vol.Optional(CONF_DOMAINS, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_ENTITY_GLOBS, default=[]): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(CONF_ENTITIES, default=[]): cv.entity_ids,
    }
)

INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_INCLUDE, default=INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER({})
        ): INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
        vol.Optional(
            CONF_EXCLUDE, default=INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER({})
        ): INCLUDE_EXCLUDE_FILTER_SCHEMA_INNER,
    }
)

INCLUDE_EXCLUDE_FILTER_SCHEMA = vol.All(
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA, convert_include_exclude_filter
)


def _glob_to_re(glob: str) -> Pattern[str]:
    """Translate and compile glob string into pattern."""
    return re.compile(fnmatch.translate(glob))


def _test_against_patterns(patterns: List[Pattern[str]], entity_id: str) -> bool:
    """Test entity against list of patterns, true if any match."""
    for pattern in patterns:
        if pattern.match(entity_id):
            return True

    return False


# It's safe since we don't modify it. And None causes typing warnings
# pylint: disable=dangerous-default-value
def generate_filter(
    include_domains: List[str],
    include_entities: List[str],
    exclude_domains: List[str],
    exclude_entities: List[str],
    include_entity_globs: List[str] = [],
    exclude_entity_globs: List[str] = [],
) -> Callable[[str], bool]:
    """Return a function that will filter entities based on the args."""
    include_d = set(include_domains)
    include_e = set(include_entities)
    exclude_d = set(exclude_domains)
    exclude_e = set(exclude_entities)
    include_eg_set = set(include_entity_globs)
    exclude_eg_set = set(exclude_entity_globs)
    include_eg = list(map(_glob_to_re, include_eg_set))
    exclude_eg = list(map(_glob_to_re, exclude_eg_set))

    have_exclude = bool(exclude_e or exclude_d or exclude_eg)
    have_include = bool(include_e or include_d or include_eg)

    def entity_included(domain: str, entity_id: str) -> bool:
        """Return true if entity matches inclusion filters."""
        return (
            entity_id in include_e
            or domain in include_d
            or bool(include_eg and _test_against_patterns(include_eg, entity_id))
        )

    def entity_excluded(domain: str, entity_id: str) -> bool:
        """Return true if entity matches exclusion filters."""
        return (
            entity_id in exclude_e
            or domain in exclude_d
            or bool(exclude_eg and _test_against_patterns(exclude_eg, entity_id))
        )

    # Case 1 - no includes or excludes - pass all entities
    if not have_include and not have_exclude:
        return lambda entity_id: True

    # Case 2 - includes, no excludes - only include specified entities
    if have_include and not have_exclude:

        def entity_filter_2(entity_id: str) -> bool:
            """Return filter function for case 2."""
            domain = split_entity_id(entity_id)[0]
            return entity_included(domain, entity_id)

        return entity_filter_2

    # Case 3 - excludes, no includes - only exclude specified entities
    if not have_include and have_exclude:

        def entity_filter_3(entity_id: str) -> bool:
            """Return filter function for case 3."""
            domain = split_entity_id(entity_id)[0]
            return not entity_excluded(domain, entity_id)

        return entity_filter_3

    # Case 4 - both includes and excludes specified
    # Case 4a - include domain or glob specified
    #  - if domain is included, pass if entity not excluded
    #  - if glob is included, pass if entity and domain not excluded
    #  - if domain and glob are not included, pass if entity is included
    # note: if both include domain matches then exclude domains ignored.
    #   If glob matches then exclude domains and glob checked
    if include_d or include_eg:

        def entity_filter_4a(entity_id: str) -> bool:
            """Return filter function for case 4a."""
            domain = split_entity_id(entity_id)[0]
            if domain in include_d:
                return not (
                    entity_id in exclude_e
                    or bool(
                        exclude_eg and _test_against_patterns(exclude_eg, entity_id)
                    )
                )
            if _test_against_patterns(include_eg, entity_id):
                return not entity_excluded(domain, entity_id)
            return entity_id in include_e

        return entity_filter_4a

    # Case 4b - exclude domain or glob specified, include has no domain or glob
    # In this one case the traditional include logic is inverted. Even though an
    # include is specified since its only a list of entity IDs its used only to
    # expose specific entities excluded by domain or glob. Any entities not
    # excluded are then presumed included. Logic is as follows
    #  - if domain or glob is excluded, pass if entity is included
    #  - if domain is not excluded, pass if entity not excluded by ID
    if exclude_d or exclude_eg:

        def entity_filter_4b(entity_id: str) -> bool:
            """Return filter function for case 4b."""
            domain = split_entity_id(entity_id)[0]
            if domain in exclude_d or (
                exclude_eg and _test_against_patterns(exclude_eg, entity_id)
            ):
                return entity_id in include_e
            return entity_id not in exclude_e

        return entity_filter_4b

    # Case 4c - neither include or exclude domain specified
    #  - Only pass if entity is included.  Ignore entity excludes.
    return lambda entity_id: entity_id in include_e
