"""
Search the audio on YT
"""
import asyncio
import json
import logging

import requests

from homeassistant.components import ais_cloud, ais_updater
from homeassistant.components.ais_dom import ais_global

aisCloud = None
URL_BASE = "https://www.googleapis.com/youtube/v3/search"
DEFAULT_ACTION = "No video"

DOMAIN = "ais_yt_service"
SERVICE_SEARCH = "search"
ATTR_QUERY = "query"
ATTR_NAME = "name"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    global aisCloud
    aisCloud = ais_cloud.AisCloudWS(hass)
    """Register the service."""
    data = hass.data[DOMAIN] = YouTubeData(hass)
    await data.async_get_key(hass)

    async def async_search(service):
        """search service about audio"""
        await data.async_process_search(service)

    def select_track_uri(service):
        """select track uri"""
        data.process_select_track_uri(service)

    # register services
    hass.services.async_register(DOMAIN, SERVICE_SEARCH, async_search)
    hass.services.async_register(DOMAIN, "select_track_uri", select_track_uri)

    return True


class YouTubeData:
    """Class to hold YT data."""

    def __init__(self, hass):
        """Initialize the radio stations."""
        self.hass = hass
        self.yt_key = None

    async def async_get_key(self, hass):
        try:
            json_ws_resp = await aisCloud.async_key("ytsearch")
            self.yt_key = json_ws_resp["key"]
        except Exception as e:
            _LOGGER.error("ais_yt_service async_get_key: " + str(e))
            ais_global.G_OFFLINE_MODE = True

    async def async_get_new_key(self, old_key, query, prev_page_token, next_page_token):
        try:
            json_ws_resp = await aisCloud.async_new_key("ytsearch", old_key)
            self.yt_key = json_ws_resp["key"]
        except Exception as e:
            _LOGGER.error("YouTube " + str(e))

        # check if new key is new (different from old one)
        if self.yt_key != old_key:
            # call the service again
            await self.hass.services.async_call(
                "ais_yt_service",
                "search",
                {
                    ATTR_QUERY: query,
                    "prevPageToken": prev_page_token,
                    "nextPageToken": next_page_token,
                },
            )

    async def async_process_search(self, call):
        """Search in service."""
        query = None
        prev_page_token = None
        next_page_token = None
        text = None
        if ATTR_QUERY in call.data:
            query = call.data[ATTR_QUERY]

        if "prevPageToken" in call.data:
            if call.data["prevPageToken"] is not None:
                prev_page_token = call.data["prevPageToken"].replace(
                    "prevPageToken_", ""
                )

        if "nextPageToken" in call.data:
            if call.data["nextPageToken"] is not None:
                next_page_token = call.data["nextPageToken"].replace(
                    "nextPageToken_", ""
                )

        if (
            (query is None or len(query.strip()) == 0)
            and prev_page_token is None
            and next_page_token is None
        ):
            # get tracks from favorites
            await self.hass.services.async_call(
                "ais_bookmarks",
                "get_favorites",
                {"audio_source": ais_global.G_AN_MUSIC},
            )
            return

        if self.yt_key is None:
            try:
                json_ws_resp = await aisCloud.async_key("ytsearch")
                self.yt_key = json_ws_resp["key"]
            except Exception as e:
                ais_global.G_OFFLINE_MODE = True
                await self.hass.services.async_call(
                    "ais_ai_service",
                    "say_it",
                    {"text": "Brak odpowiedzi, sprawdź połączenie z Intenetem"},
                )
                _LOGGER.error("process_search_async " + str(e))
                return

        params = dict(
            order="relevance",
            part="snippet",
            key=self.yt_key,
            maxResults=10,
            type="video",
            fields="items/id/videoId, items/snippet/title, items/snippet/thumbnails/medium/url, "
            "pageInfo/totalResults, nextPageToken, prevPageToken",
        )
        params.update({"q": query})
        if prev_page_token is not None:
            params.update({"pageToken": prev_page_token})
        if next_page_token is not None:
            params.update({"pageToken": next_page_token})
        data = requests.get(URL_BASE, params=params).json()

        # check if error
        if "error" in data:
            for error in data["error"]["errors"]:
                if error["reason"] == "quotaExceeded":
                    # get the new token and try again
                    await self.async_get_new_key(
                        self.yt_key, query, prev_page_token, next_page_token
                    )
                    return

                if text is None:
                    text = error["message"]
                else:
                    text = text + " " + error["message"]
            await self.hass.services.async_call(
                "ais_ai_service", "say_it", {"text": text}
            )
            return

        list_info = {}
        list_idx = 0

        total_results = 0
        if "pageInfo" in data:
            total_results = data["pageInfo"]["totalResults"]

        if "prevPageToken" in data:
            list_info[list_idx] = {}
            list_info[list_idx][
                "title"
            ] = "pobierz poprzednią stronę wyników wyszukiwania"
            list_info[list_idx][
                "name"
            ] = "pobierz poprzednią stronę wyników wyszukiwania"
            list_info[list_idx]["thumbnail"] = "/static/icons/favicon-100x100.png"
            list_info[list_idx]["uri"] = "prevPageToken_" + data["prevPageToken"]
            list_info[list_idx]["media_source"] = ais_global.G_AN_MUSIC
            list_info[list_idx]["audio_type"] = ais_global.G_AN_MUSIC
            list_info[list_idx]["icon"] = "mdi:page-previous"
            list_info[list_idx]["editable"] = True
            list_info[list_idx]["query"] = query
            list_idx = list_idx + 1

        if "items" in data:
            for item in data["items"]:
                list_info[list_idx] = {}
                list_info[list_idx]["title"] = item["snippet"]["title"]
                list_info[list_idx]["name"] = item["snippet"]["title"]
                # item['snippet']['description']
                list_info[list_idx]["thumbnail"] = item["snippet"]["thumbnails"][
                    "medium"
                ]["url"]
                list_info[list_idx]["uri"] = item["id"]["videoId"]
                list_info[list_idx]["media_source"] = ais_global.G_AN_MUSIC
                list_info[list_idx]["audio_type"] = ais_global.G_AN_MUSIC
                list_info[list_idx]["icon"] = "mdi:play"
                list_info[list_idx]["editable"] = True
                list_idx = list_idx + 1

        if "nextPageToken" in data:
            list_info[list_idx] = {}
            list_info[list_idx][
                "title"
            ] = "pobierz następną stronę wyników wyszukiwania"
            list_info[list_idx]["name"] = "pobierz następną stronę wyników wyszukiwania"
            list_info[list_idx]["thumbnail"] = "/static/icons/favicon-100x100.png"
            list_info[list_idx]["uri"] = "nextPageToken_" + data["nextPageToken"]
            list_info[list_idx]["media_source"] = ais_global.G_AN_MUSIC
            list_info[list_idx]["audio_type"] = ais_global.G_AN_MUSIC
            list_info[list_idx]["icon"] = "mdi:page-next"
            list_info[list_idx]["editable"] = True
            list_info[list_idx]["query"] = query

        # update list
        self.hass.states.async_set("sensor.youtubelist", -1, list_info)
        if len(list_info) > 0:
            # from remote
            import homeassistant.components.ais_ai_service as ais_ai

            if (
                ais_ai.CURR_ENTITIE == "input_text.ais_music_query"
                and ais_ai.CURR_BUTTON_CODE == 4
            ):
                ais_ai.set_curr_entity(self.hass, "sensor.youtubelist")
                ais_ai.CURR_ENTITIE_ENTERED = True
                text = "Znaleziono: %s, wybierz pozycję którą mam włączyć" % (
                    str(total_results)
                )
            else:
                if next_page_token is None and prev_page_token is None:
                    text = "Znaleziono: {}, włączam pierwszy: {}".format(
                        str(total_results), list_info[0]["title"]
                    )
                    await self.hass.services.async_call(
                        "ais_yt_service", "select_track_uri", {"id": 0}
                    )

                if ais_ai.CURR_ENTITIE == "media_player.wbudowany_glosnik":
                    if next_page_token is not None and ais_ai.CURR_BUTTON_CODE == 22:
                        text = (
                            "Pobrano następną stronę wyników, włączam pierwszy: %s"
                            % (list_info[1]["title"])
                        )
                        await self.hass.services.async_call(
                            "ais_yt_service", "select_track_uri", {"id": 1}
                        )
                    elif prev_page_token is not None and ais_ai.CURR_BUTTON_CODE == 21:
                        text = (
                            "Pobrano poprzednią stronę wyników, włączam ostatni: %s"
                            % (list_info[len(list_info) - 2]["title"])
                        )
                        await self.hass.services.async_call(
                            "ais_yt_service",
                            "select_track_uri",
                            {"id": len(list_info) - 2},
                        )

        else:
            text = "Brak wnyników na YouTube dla zapytania %s" % query
        # info to user
        if text is not None:
            await self.hass.services.async_call(
                "ais_ai_service", "say_it", {"text": text}
            )

    def process_select_track_uri(self, call):
        _LOGGER.debug("process_select_track_uri")
        # """play track by id on sensor list."""
        call_id = call.data["id"]
        list_sensor = "sensor.youtubelist"
        media_source = ais_global.G_AN_MUSIC
        if "media_source" in call.data:
            media_source = call.data["media_source"]
            if media_source == ais_global.G_AN_FAVORITE:
                list_sensor = "sensor.aisfavoriteslist"
            elif media_source == ais_global.G_AN_BOOKMARK:
                list_sensor = "sensor.aisbookmarkslist"

        state = self.hass.states.get(list_sensor)
        attr = state.attributes
        track = attr.get(int(call_id))
        media_position_ms = track.get("media_position_ms", 0)
        url = "https://www.youtube.com/watch?v="
        # update list
        self.hass.states.async_set(list_sensor, call_id, attr)

        # get prev / next results
        if track["uri"].startswith("prevPageToken_"):
            self.hass.services.call(
                "ais_yt_service",
                "search",
                {"prevPageToken": track["uri"], "query": track["query"]},
            )
            return
        if track["uri"].startswith("nextPageToken_"):
            self.hass.services.call(
                "ais_yt_service",
                "search",
                {"nextPageToken": track["uri"], "query": track["query"]},
            )
            return

        # try to get media url from AIS cloud
        media_url = None
        try:
            local_extractor_version = ais_updater.get_package_version("youtube_dl")
            ws_resp = aisCloud.extract_media(
                url + track["uri"], local_extractor_version
            )
            json_ws_resp = ws_resp.json()
            cloud_extractor_version = json_ws_resp["extractor_version"]
            if "youtube_dl==" + cloud_extractor_version != local_extractor_version:
                self.hass.services.call(
                    "ais_updater",
                    "upgrade_package",
                    {"package": "youtube_dl", "version": cloud_extractor_version},
                )
            media_url = json_ws_resp["url"]
        except Exception as e:
            # currently this is normal case
            _LOGGER.debug("extract_media Exception: " + str(e))

        all_ok = False
        if media_url is not None and len(media_url) > 0:
            # check 403
            import requests

            try:
                r = requests.head(media_url, allow_redirects=True, timeout=1)
                if r.status_code < 400:
                    all_ok = True
            except Exception as e:
                _LOGGER.warning("Request to youtube error " + str(e))

        if all_ok:
            # set stream url, image and title
            _audio_info = json.dumps(
                {
                    "IMAGE_URL": track["thumbnail"],
                    "NAME": track["title"],
                    "lookup_url": track["uri"],
                    "MEDIA_SOURCE": media_source,
                    "media_content_id": media_url,
                    "media_position_ms": media_position_ms,
                }
            )
            self.hass.services.call(
                "media_player",
                "play_media",
                {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_content_info",
                    "media_content_id": _audio_info,
                },
            )
        else:
            # use media_extractor to extract locally
            self.hass.services.call(
                "media_extractor",
                "play_media",
                {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_id": url + track["uri"],
                    "media_content_type": "video/youtube",
                },
            )

            # set stream image and title
            _audio_info = json.dumps(
                {
                    "IMAGE_URL": track["thumbnail"],
                    "NAME": track["title"],
                    "MEDIA_SOURCE": ais_global.G_AN_MUSIC,
                    "lookup_url": track["uri"],
                }
            )
            self.hass.services.call(
                "media_player",
                "play_media",
                {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_info",
                    "media_content_id": _audio_info,
                },
            )
