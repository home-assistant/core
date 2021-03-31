"""Component to manage a shopping list."""
import asyncio
import json
import logging
import uuid

import homeassistant.components.ais_dom.ais_global as ais_global
from homeassistant.core import callback
from homeassistant.helpers import intent
from homeassistant.util.json import load_json, save_json

DOMAIN = "ais_bookmarks"
DEPENDENCIES = ["http"]
_LOGGER = logging.getLogger(__name__)
INTENT_ADD_FAVORITE = "AisBookmarksAddFavorite"
INTENT_ADD_BOOKMARK = "AisBookmarksAddBookmark"
INTENT_LAST_BOOKMARKS = "AisBookmarksLastBookmarks"
INTENT_PLAY_LAST_BOOKMARK = "AisBookmarkPlayLastBookmark"
PERSISTENCE_BOOKMARKS = ".dom/.ais_bookmarks.json"
PERSISTENCE_FAVORITES = ".dom/.ais_favorites.json"

SERVICE_ADD_BOOKMARK = "add_bookmark"
SERVICE_ADD_FAVORITE = "add_favorite"
SERVICE_GET_BOOKMARKS = "get_bookmarks"
SERVICE_GET_FAVORITES = "get_favorites"
SERVICE_PLAY_BOOKMARK = "play_bookmark"
SERVICE_PLAY_FAVORITE = "play_favorite"
SERVICE_DELETE_BOOKMARK = "delete_bookmark"
SERVICE_DELETE_FAVORITE = "delete_favorite"


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize the ais bookmarks list."""

    @asyncio.coroutine
    def add_bookmark_service(call):
        """Add an current played item to bookmark"""
        d = hass.data[DOMAIN]
        d.async_add(call, True)

    @asyncio.coroutine
    def add_favorite_service(call):
        """Add an current played item to favorite."""
        d = hass.data[DOMAIN]
        d.async_add(call, False)

    @asyncio.coroutine
    def get_bookmarks_service(call):
        """Return the list of bookmarks to app list"""
        d = hass.data[DOMAIN]
        list_info = {}
        list_idx = 0
        for item in reversed(d.bookmarks):
            if "media_stream_image" in item and item["media_stream_image"] is not None:
                img = item["media_stream_image"]
            else:
                img = "/static/icons/tile-win-310x150.png"
            list_info[list_idx] = {}
            list_info[list_idx]["title"] = item["name"]
            if item["name"].startswith(item["source"]):
                list_info[list_idx]["name"] = item["name"]
            else:
                list_info[list_idx]["name"] = (
                    ais_global.G_NAME_FOR_AUDIO_NATURE.get(
                        item["source"], item["source"]
                    )
                    + " "
                    + item["name"]
                )
            list_info[list_idx]["thumbnail"] = img
            list_info[list_idx]["uri"] = item["media_content_id"]
            list_info[list_idx]["audio_type"] = item["source"]
            list_info[list_idx]["media_source"] = item["source"]
            list_info[list_idx]["icon"] = "mdi:bookmark-music"
            list_info[list_idx]["icon_remove"] = "mdi:delete-forever"
            list_info[list_idx]["editable"] = True
            list_info[list_idx]["id"] = item["id"]
            list_info[list_idx][
                "media_position"
            ] = ais_global.get_milliseconds_formated(item["media_position"])
            list_info[list_idx]["media_position_ms"] = item["media_position"]
            list_idx = list_idx + 1
        # create lists
        hass.states.async_set("sensor.aisbookmarkslist", -1, list_info)

    @asyncio.coroutine
    def get_favorites_service(call):
        """Return the list of favorites to app list"""
        audio_source = None
        if "audio_source" in call.data:
            audio_source = call.data["audio_source"]

        d = hass.data[DOMAIN]
        list_info = {}
        list_idx = 0
        for item in reversed(d.favorites):
            if audio_source is None or audio_source == item["source"]:
                if (
                    "media_stream_image" in item
                    and item["media_stream_image"] is not None
                ):
                    img = item["media_stream_image"]
                else:
                    img = "/static/icons/tile-win-310x150.png"
                list_info[list_idx] = {}
                list_info[list_idx]["title"] = item["name"]
                if item["name"].startswith(item["source"]):
                    list_info[list_idx]["name"] = item["name"]
                else:
                    list_info[list_idx]["name"] = (
                        ais_global.G_NAME_FOR_AUDIO_NATURE.get(
                            item["source"], item["source"]
                        )
                        + " "
                        + item["name"]
                    )
                list_info[list_idx]["thumbnail"] = img
                list_info[list_idx]["uri"] = item["media_content_id"]
                list_info[list_idx]["audio_type"] = item["source"]
                list_info[list_idx]["icon_type"] = ais_global.G_ICON_FOR_AUDIO.get(
                    item["source"], "mdi:play"
                )
                list_info[list_idx]["icon_remove"] = "mdi:delete-forever"
                list_info[list_idx]["editable"] = True
                if audio_source == ais_global.G_AN_PODCAST:
                    list_info[list_idx]["icon"] = "mdi:podcast"
                else:
                    list_info[list_idx]["icon"] = "mdi:play"
                list_info[list_idx]["id"] = item["id"]
                list_idx = list_idx + 1

        # create lists
        if audio_source is None:
            # get all items
            hass.states.async_set("sensor.aisfavoriteslist", -1, list_info)
        else:
            # check if the change was done form remote
            import homeassistant.components.ais_ai_service as ais_ai

            if audio_source == ais_global.G_AN_RADIO:
                hass.states.async_set("sensor.radiolist", -1, list_info)
                if (
                    ais_ai.CURR_ENTITIE == "input_select.radio_type"
                    and ais_ai.CURR_BUTTON_CODE == 23
                ):
                    ais_ai.set_curr_entity(hass, "sensor.radiolist")
                    hass.async_add_job(
                        hass.services.async_call(
                            "ais_ai_service", "say_it", {"text": "Wybierz stację"}
                        )
                    )
            elif audio_source == ais_global.G_AN_PODCAST:
                hass.states.async_set("sensor.podcastnamelist", -1, list_info)
                if (
                    ais_ai.CURR_ENTITIE == "input_select.podcast_type"
                    and ais_ai.CURR_BUTTON_CODE == 23
                ):
                    ais_ai.set_curr_entity(hass, "sensor.podcastnamelist")
                    hass.async_add_job(
                        hass.services.async_call(
                            "ais_ai_service", "say_it", {"text": "Wybierz audycję"}
                        )
                    )
            elif audio_source == ais_global.G_AN_MUSIC:
                hass.states.async_set("sensor.youtubelist", -1, list_info)
            elif audio_source == ais_global.G_AN_SPOTIFY:
                hass.states.async_set("sensor.spotifylist", -1, list_info)
            elif audio_source == ais_global.G_AN_AUDIOBOOK:
                hass.states.async_set("sensor.audiobookschapterslist", -1, list_info)

    @asyncio.coroutine
    def play_bookmark_service(call):
        """Play selected bookmark"""
        bookmark_id = int(call.data.get("id"))
        # get item from list
        state = hass.states.get("sensor.aisbookmarkslist")
        attr = state.attributes
        track = attr.get(bookmark_id)

        #
        if track["media_source"] == ais_global.G_AN_LOCAL:
            last_slash = track["uri"].rfind("/")
            if last_slash > 0:
                dir_path = track["uri"][0:last_slash]
            else:
                dir_path = track["uri"]
            hass.async_add_job(
                hass.services.async_call(
                    "ais_drives_service",
                    "browse_path",
                    {
                        "path": dir_path,
                        "file_path": track["uri"],
                        "seek_position": track["media_position_ms"],
                    },
                )
            )

        elif track["media_source"] == ais_global.G_AN_MUSIC:
            hass.async_add_job(
                hass.services.async_call(
                    "ais_yt_service",
                    "select_track_uri",
                    {"id": bookmark_id, "media_source": ais_global.G_AN_BOOKMARK},
                )
            )
        else:
            _audio_info = json.dumps(
                {
                    "IMAGE_URL": track["thumbnail"],
                    "NAME": track["title"],
                    "audio_type": track["audio_type"],
                    "MEDIA_SOURCE": track["media_source"],
                    "media_content_id": track["uri"],
                    "media_position_ms": track["media_position_ms"],
                }
            )
            # set stream uri, image and title
            hass.async_add_job(
                hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                        "media_content_type": "ais_content_info",
                        "media_content_id": _audio_info,
                    },
                )
            )

    @asyncio.coroutine
    def play_favorite_service(call):
        """Play selected favorite"""
        favorite_id = int(call.data.get("id"))
        # get item from list
        state = hass.states.get("sensor.aisfavoriteslist")
        attr = state.attributes
        track = attr.get(favorite_id)

        _audio_info = json.dumps(
            {
                "IMAGE_URL": track["thumbnail"],
                "NAME": track["title"],
                "audio_type": track["audio_type"],
                "MEDIA_SOURCE": ais_global.G_AN_FAVORITE,
                "media_content_id": track["uri"],
            }
        )
        # set stream uri, image and title
        hass.async_add_job(
            hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID,
                    "media_content_type": "ais_content_info",
                    "media_content_id": _audio_info,
                },
            )
        )

    @asyncio.coroutine
    def delete_bookmark_service(call):
        """Delete selected bookmark"""
        bookmark_id = int(call.data.get("id"))
        state = hass.states.get("sensor.aisbookmarkslist")
        attr = state.attributes
        track = attr.get(bookmark_id)
        d = hass.data[DOMAIN]
        d.async_remove_bookmark(track["id"], True)

    @asyncio.coroutine
    def delete_favorite_service(call):
        """Delete selected favorite"""
        favorite_id = int(call.data.get("id"))
        state = hass.states.get("sensor.aisfavoriteslist")
        attr = state.attributes
        track = attr.get(favorite_id)
        d = hass.data[DOMAIN]
        d.async_remove_bookmark(track["id"], False)

    data = hass.data[DOMAIN] = BookmarksData(hass)
    intent.async_register(hass, AddFavoriteIntent())
    intent.async_register(hass, AddBookmarkIntent())
    intent.async_register(hass, ListTopBookmarkIntent())
    intent.async_register(hass, PlayLastBookmarkIntent())
    hass.services.async_register(DOMAIN, SERVICE_ADD_BOOKMARK, add_bookmark_service)
    hass.services.async_register(DOMAIN, SERVICE_ADD_FAVORITE, add_favorite_service)
    hass.services.async_register(DOMAIN, SERVICE_GET_BOOKMARKS, get_bookmarks_service)
    hass.services.async_register(DOMAIN, SERVICE_GET_FAVORITES, get_favorites_service)
    hass.services.async_register(DOMAIN, SERVICE_PLAY_BOOKMARK, play_bookmark_service)
    hass.services.async_register(DOMAIN, SERVICE_PLAY_FAVORITE, play_favorite_service)
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_BOOKMARK, delete_bookmark_service
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_FAVORITE, delete_favorite_service
    )

    hass.components.conversation.async_register(
        INTENT_ADD_FAVORITE, ["Dodaj do ulubionych", "Do ulubionych", "Lubię to"]
    )
    hass.components.conversation.async_register(
        INTENT_ADD_BOOKMARK, ["Dodaj zakładkę", "Zakładka"]
    )
    hass.components.conversation.async_register(
        INTENT_LAST_BOOKMARKS, ["Jakie mam zakładki", "Jakie są zakładki"]
    )
    hass.components.conversation.async_register(
        INTENT_PLAY_LAST_BOOKMARK,
        ["Włącz ostatnią zakładkę", "Włącz zakładkę", "Ostatnia zakładka"],
    )

    yield from data.async_load()

    hass.states.async_set("sensor.aisbookmarkslist", -1, {})
    hass.states.async_set("sensor.aisfavoriteslist", -1, {})

    return True


class BookmarksData:
    """Class to hold bookmarks list data."""

    def __init__(self, hass):
        """Initialize the bookmarks list."""
        self.hass = hass
        self.bookmarks = []
        self.favorites = []

    @callback
    def async_add(self, call, bookmark):
        """Add a item."""
        voice_call = False
        if "voice_call" in call.data:
            voice_call = True

        if bookmark and "attr" not in call.data:
            # ask the player to add bookmark
            self.hass.async_add_job(
                self.hass.services.async_call(
                    "ais_ai_service",
                    "publish_command_to_frame",
                    {"key": "addBookmark", "val": True},
                )
            )
            self.hass.async_add_job(
                self.hass.services.async_call(
                    "ais_ai_service", "say_it", {"text": "Zakładka"}
                )
            )
            return

        attributes = {}
        if "attr" in call.data:
            attributes = call.data["attr"]
            name = attributes.get("media_title").strip()
            source = attributes.get("source").strip()
            media_position = attributes.get("media_position", 0)
            media_content_id = attributes.get("media_content_id")
        else:
            state = self.hass.states.get(ais_global.G_LOCAL_EXO_PLAYER_ENTITY_ID)
            attributes = state.attributes
            name = attributes.get("media_title")
            source = attributes.get("source")
            media_position = attributes.get("media_position", 0)
            media_content_id = attributes.get("media_content_id")
        try:
            media_stream_image = ais_global.G_CURR_MEDIA_CONTENT["IMAGE_URL"]
        except Exception:
            media_stream_image = "/static/icons/favicon-100x100.png"

        try:
            audio_type = ais_global.G_CURR_MEDIA_CONTENT["audio_type"]
        except Exception:
            audio_type = source
        audio_type_pl = ais_global.G_NAME_FOR_AUDIO_NATURE.get(audio_type, audio_type)

        if name is None or source is None or media_content_id is None:
            _LOGGER.warning(
                "can't add the bookmark, no full info provided " + str(attributes)
            )
            return

        if bookmark:
            # type validation
            if audio_type == ais_global.G_AN_RADIO:
                message = f"Nie można dodać zakładki do {audio_type_pl}"
                self.hass.async_add_job(
                    self.hass.services.async_call(
                        "ais_ai_service", "say_it", {"text": message}
                    )
                )
                return

            #
            full_name = name
            if audio_type == ais_global.G_AN_LOCAL:
                media_content_id = ais_global.G_CURR_MEDIA_CONTENT["lookup_url"]
                full_name = ais_global.G_CURR_MEDIA_CONTENT["ALBUM_NAME"] + " " + name
            # if yt then not bookmark to current search but to lookup url
            elif audio_type == ais_global.G_AN_MUSIC:
                media_content_id = ais_global.G_CURR_MEDIA_CONTENT["lookup_url"]

            # check if the audio is on bookmark list
            item = next(
                (
                    itm
                    for itm in self.bookmarks
                    if (itm["media_content_id"] == media_content_id)
                ),
                None,
            )
            if item is not None:
                # delete the old bookmark
                self.async_remove_bookmark(item["id"], True)
                message = f"Przesuwam zakładkę {full_name}"
            else:
                message = f"Dodaję nową zakładkę {full_name}"

            # add the bookmark
            item = {
                "name": full_name,
                "id": uuid.uuid4().hex,
                "source": audio_type,
                "media_position": media_position,
                "media_content_id": media_content_id,
                "media_stream_image": media_stream_image,
            }
            self.bookmarks.append(item)
            self.hass.async_add_job(self.save, True)
            if voice_call:
                self.hass.async_add_job(
                    self.hass.services.async_call(
                        "ais_ai_service", "say_it", {"text": message}
                    )
                )
            else:
                _LOGGER.info(message)
            return item
        else:
            # validation
            if source == ais_global.G_AN_FAVORITE:
                message = f"{audio_type_pl}, {name} jest już w ulubionych."
                self.hass.async_add_job(
                    self.hass.services.async_call(
                        "ais_ai_service", "say_it", {"text": message}
                    )
                )
                return
            # if podcast then we will add not track but audition
            if audio_type == ais_global.G_AN_PODCAST:
                media_content_id = ais_global.G_CURR_MEDIA_CONTENT["lookup_url"]
                name = ais_global.G_CURR_MEDIA_CONTENT["lookup_name"]
            elif audio_type == ais_global.G_AN_MUSIC:
                media_content_id = ais_global.G_CURR_MEDIA_CONTENT["lookup_url"]

            # check if the audio is on favorites list
            item = next(
                (
                    itm
                    for itm in self.favorites
                    if (itm["name"] == name and itm["source"] == audio_type)
                ),
                None,
            )
            if item is not None:
                message = f"{audio_type_pl}, {name} jest już w ulubionych."
                self.hass.async_add_job(
                    self.hass.services.async_call(
                        "ais_ai_service", "say_it", {"text": message}
                    )
                )
                return
            # add item
            item = {
                "name": name,
                "id": uuid.uuid4().hex,
                "source": source,
                "media_content_id": media_content_id,
                "media_stream_image": media_stream_image,
            }
            self.favorites.append(item)
            self.hass.async_add_job(self.save, False)
            message = "Dobrze zapamiętam - dodaje {} {} do Twoich ulubionych".format(
                audio_type_pl, name
            )
            self.hass.async_add_job(
                self.hass.services.async_call(
                    "ais_ai_service", "say_it", {"text": message}
                )
            )
            return item

    @callback
    def async_update(self, item_id, info):
        """Update a bookmarks list item."""
        item = next((itm for itm in self.bookmarks if itm["id"] == item_id), None)

        if item is None:
            raise KeyError

        item.update(info)
        self.hass.async_add_job(self.save)
        return item

    @callback
    def async_remove_bookmark(self, item_id, bookmark):
        if bookmark:
            """Reemove bookmark """
            self.bookmarks = [itm for itm in self.bookmarks if not itm["id"] == item_id]
            self.hass.async_add_job(self.save, True)
        else:
            """Reemove favorites """
            self.favorites = [itm for itm in self.favorites if not itm["id"] == item_id]
            self.hass.async_add_job(self.save, False)

    @asyncio.coroutine
    def async_load(self):
        """Load bookmarks."""

        def load():
            """Load the bookmarks synchronously."""
            try:
                self.bookmarks = load_json(
                    self.hass.config.path(PERSISTENCE_BOOKMARKS), default=[]
                )
                self.favorites = load_json(
                    self.hass.config.path(PERSISTENCE_FAVORITES), default=[]
                )
            except Exception as e:
                _LOGGER.error("Can't load bookmarks data: " + str(e))

        yield from self.hass.async_add_job(load)

    def save(self, bookmark):
        """Save the bookmarks and favorites."""
        if bookmark:
            self.bookmarks = self.bookmarks[-50:]
            save_json(self.hass.config.path(PERSISTENCE_BOOKMARKS), self.bookmarks)
            self.hass.async_add_job(
                self.hass.services.async_call(DOMAIN, SERVICE_GET_BOOKMARKS)
            )
        else:
            self.favorites = self.favorites[-50:]
            save_json(self.hass.config.path(PERSISTENCE_FAVORITES), self.favorites)
            self.hass.async_add_job(
                self.hass.services.async_call(DOMAIN, SERVICE_GET_FAVORITES)
            )


class AddFavoriteIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_ADD_FAVORITE

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        state = hass.states.get("media_player.wbudowany_glosnik")
        name = state.attributes.get("media_title")
        source = state.attributes.get("source")
        media_content_id = state.attributes.get("media_content_id")
        # check if all fields are provided
        if name is None or source is None or media_content_id is None:
            answer = (
                "Nie można dodać do ulubionych - brak informacji o odtwarzanym audio."
            )
        else:
            answer = f"Dobrze zapamiętam - dodaje {name} do Twoich ulubionych"
            # hass.data[DOMAIN].async_add(state.attributes, False)
            yield from hass.services.async_call(
                "ais_bookmarks", "add_favorite", {"voice_call": True}
            )
        response = intent_obj.create_response()
        response.async_set_speech(answer)
        return response


class AddBookmarkIntent(intent.IntentHandler):
    """Handle AddItem intents."""

    intent_type = INTENT_ADD_BOOKMARK

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        state = hass.states.get("media_player.wbudowany_glosnik")
        name = state.attributes.get("media_title")
        source = state.attributes.get("source")
        media_content_id = state.attributes.get("media_content_id")
        # check if all fields are provided
        if name is None or source is None or media_content_id is None:
            answer = "Nie można dodać zakładki - brak informacji o odtwarzanym audio."
        else:
            answer = f"Dobrze dodaję zakładkę {name}"
            yield from hass.services.async_call(
                "ais_bookmarks", "add_bookmark", {"voice_call": True}
            )
        response = intent_obj.create_response()
        response.async_set_speech(answer)
        return response


class ListTopBookmarkIntent(intent.IntentHandler):
    """Handle ListTopBookmarkIntent intents."""

    intent_type = INTENT_LAST_BOOKMARKS

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        bookmarks = intent_obj.hass.data[DOMAIN].bookmarks[-5:]
        response = intent_obj.create_response()
        if not bookmarks:
            answer = "Nie ma żadnych zakładek"
        else:
            answer = "Oto ostatnie {} zakładki na twojej liście: {}".format(
                min(len(bookmarks), 5),
                ", ".join(itm["name"] for itm in reversed(bookmarks)),
            )
        response.async_set_speech(answer)
        yield from hass.services.async_call(
            "ais_ai_service", "say_it", {"text": answer}
        )
        return response


class PlayLastBookmarkIntent(intent.IntentHandler):
    """Handle PlayLastBookmarkIntent intents."""

    intent_type = INTENT_PLAY_LAST_BOOKMARK

    @asyncio.coroutine
    def async_handle(self, intent_obj):
        """Handle the intent."""
        hass = intent_obj.hass
        bookmarks = intent_obj.hass.data[DOMAIN].bookmarks[-1:]
        response = intent_obj.create_response()
        if not bookmarks:
            answer = "Nie ma żadnych zakładek"
        else:
            bookmark = bookmarks[0]["source"] + "; " + bookmarks[0]["name"]
            answer = f"Włączam ostatnią zakładkę {bookmark}"
            yield from hass.services.async_call(
                "ais_bookmarks", "play_bookmark", {"bookmark": bookmark}
            )
        response.async_set_speech(answer)
        yield from hass.services.async_call(
            "ais_ai_service", "say_it", {"text": answer}
        )
        return response
