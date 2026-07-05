"""Immich as a media source."""

from logging import getLogger
from typing import TypedDict, override

from aiohttp.web import HTTPNotFound, Request, Response, StreamResponse
from aioimmich.assets.models import AssetType, ImmichAsset
from aioimmich.exceptions import ImmichError, ImmichForbiddenError

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import (
    BrowseError,
    MediaClass,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import ChunkAsyncStreamIterator

from .const import DOMAIN
from .coordinator import ImmichConfigEntry

LOGGER = getLogger(__name__)


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Immich media source."""
    hass.http.register_view(ImmichMediaView(hass))
    return ImmichMediaSource(hass)


class ImmichMediaSourceIdentifier:
    """Immich media item identifier."""

    def __init__(self, identifier: str) -> None:
        """Split identifier into parts."""
        parts = identifier.split("|")
        # config_entry.unique_id|collection|collection_id|asset_id|file_name|mime_type
        self.unique_id = parts[0]
        self.collection = parts[1] if len(parts) > 1 else None
        self.collection_id = parts[2] if len(parts) > 2 else None
        self.asset_id = parts[3] if len(parts) > 3 else None
        self.file_name = parts[4] if len(parts) > 3 else None
        self.mime_type = parts[5] if len(parts) > 3 else None


class ImmichSmartSearchArgs(TypedDict, total=False):
    """Type for smart search arguments."""

    query: str
    asset_type: AssetType
    album_ids: list[str]
    person_ids: list[str]
    tag_ids: list[str]
    is_favorite: bool
    is_not_in_album: bool


MEDIA_CLASS_ASSET_TYPE_MAPPING = {
    MediaClass.IMAGE: AssetType.IMAGE,
    MediaClass.VIDEO: AssetType.VIDEO,
}


def _parse_assets(
    assets: list[ImmichAsset], identifier: ImmichMediaSourceIdentifier
) -> list[BrowseMediaSource]:
    """Parse list of ImmichAsset to list of BrowseMediaSource."""
    ret: list[BrowseMediaSource] = []
    for asset in assets:
        if not (mime_type := asset.original_mime_type) or not mime_type.startswith(
            ("image/", "video/")
        ):
            continue

        if mime_type.startswith("image/"):
            media_class = MediaClass.IMAGE
            can_play = False
            thumb_mime_type = mime_type
        else:
            media_class = MediaClass.VIDEO
            can_play = True
            thumb_mime_type = "image/jpeg"

        ret.append(
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=(
                    f"{identifier.unique_id}|"
                    f"{identifier.collection}|"
                    f"{identifier.collection_id}|"
                    f"{asset.asset_id}|"
                    f"{asset.original_file_name}|"
                    f"{mime_type}"
                ),
                media_class=media_class,
                media_content_type=mime_type,
                title=asset.original_file_name,
                can_play=can_play,
                can_expand=False,
                thumbnail=f"/immich/{identifier.unique_id}/{asset.asset_id}/thumbnail/{thumb_mime_type}",
            )
        )

    return ret


class ImmichMediaSource(MediaSource):
    """Provide Immich as media sources."""

    name = "Immich"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Immich media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    @override
    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if not (entries := self.hass.config_entries.async_loaded_entries(DOMAIN)):
            raise BrowseError(
                translation_domain=DOMAIN, translation_key="not_configured"
            )

        can_search = False
        if item.identifier:
            can_search = bool(ImmichMediaSourceIdentifier(item.identifier).unique_id)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaClass.IMAGE,
            title="Immich",
            can_play=False,
            can_expand=True,
            can_search=can_search,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                *await self._async_build_immich(item, entries),
            ],
        )

    async def _async_build_immich(
        self, item: MediaSourceItem, entries: list[ConfigEntry]
    ) -> list[BrowseMediaSource]:
        """Handle browsing different immich instances."""

        # --------------------------------------------------------
        # root level, render immich instances
        # --------------------------------------------------------
        if not item.identifier:
            LOGGER.debug("Render all Immich instances")
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=entry.unique_id,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.IMAGE,
                    title=entry.title,
                    can_play=False,
                    can_expand=True,
                )
                for entry in entries
            ]

        # --------------------------------------------------------
        # 1st level, render collections overview
        # --------------------------------------------------------
        identifier = ImmichMediaSourceIdentifier(item.identifier)
        entry: ImmichConfigEntry | None = (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, identifier.unique_id
            )
        )
        assert entry
        immich_api = entry.runtime_data.api

        if identifier.collection is None:
            LOGGER.debug("Render all collections for %s", entry.title)
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{identifier.unique_id}|{collection}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaClass.IMAGE,
                    title=collection.split("|", maxsplit=1)[0],
                    can_play=False,
                    can_expand=True,
                )
                for collection in ("albums", "favorites|favorites", "people", "tags")
            ]

        # --------------------------------------------------------
        # 2nd level, render collection
        # --------------------------------------------------------
        if identifier.collection_id is None:
            if identifier.collection == "albums":
                LOGGER.debug("Render all albums for %s", entry.title)
                try:
                    albums = await immich_api.albums.async_get_all_albums()
                except ImmichForbiddenError as err:
                    raise BrowseError(
                        translation_domain=DOMAIN,
                        translation_key="missing_api_permission",
                        translation_placeholders={"msg": str(err)},
                    ) from err
                except ImmichError:
                    return []

                return [
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{identifier.unique_id}|albums|{album.album_id}",
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaClass.IMAGE,
                        title=album.album_name,
                        can_play=False,
                        can_expand=True,
                        thumbnail=f"/immich/{identifier.unique_id}/{album.album_thumbnail_asset_id}/thumbnail/image/jpg",
                    )
                    for album in albums
                ]

            if identifier.collection == "tags":
                LOGGER.debug("Render all tags for %s", entry.title)
                try:
                    tags = await immich_api.tags.async_get_all_tags()
                except ImmichForbiddenError as err:
                    raise BrowseError(
                        translation_domain=DOMAIN,
                        translation_key="missing_api_permission",
                        translation_placeholders={"msg": str(err)},
                    ) from err
                except ImmichError:
                    return []

                return [
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{identifier.unique_id}|tags|{tag.tag_id}",
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaClass.IMAGE,
                        title=tag.name,
                        can_play=False,
                        can_expand=True,
                    )
                    for tag in tags
                ]

            if identifier.collection == "people":
                LOGGER.debug("Render all people for %s", entry.title)
                try:
                    people = await immich_api.people.async_get_all_people()
                except ImmichForbiddenError as err:
                    raise BrowseError(
                        translation_domain=DOMAIN,
                        translation_key="missing_api_permission",
                        translation_placeholders={"msg": str(err)},
                    ) from err
                except ImmichError:
                    return []

                return [
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{identifier.unique_id}|people|{person.person_id}",
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaClass.IMAGE,
                        title=person.name,
                        can_play=False,
                        can_expand=True,
                        thumbnail=f"/immich/{identifier.unique_id}/{person.person_id}/person/image/jpg",
                    )
                    for person in people
                ]

        # --------------------------------------------------------
        # final level, render assets
        # --------------------------------------------------------
        assert identifier.collection_id is not None
        assets: list[ImmichAsset] = []
        if identifier.collection == "albums":
            LOGGER.debug(
                "Render all assets of album %s for %s",
                identifier.collection_id,
                entry.title,
            )
            try:
                assets = await immich_api.search.async_get_all_by_album_ids(
                    [identifier.collection_id]
                )
            except ImmichForbiddenError as err:
                raise BrowseError(
                    translation_domain=DOMAIN,
                    translation_key="missing_api_permission",
                    translation_placeholders={"msg": str(err)},
                ) from err
            except ImmichError:
                return []

        elif identifier.collection == "tags":
            LOGGER.debug(
                "Render all assets with tag %s",
                identifier.collection_id,
            )
            try:
                assets = await immich_api.search.async_get_all_by_tag_ids(
                    [identifier.collection_id]
                )
            except ImmichForbiddenError as err:
                raise BrowseError(
                    translation_domain=DOMAIN,
                    translation_key="missing_api_permission",
                    translation_placeholders={"msg": str(err)},
                ) from err
            except ImmichError:
                return []

        elif identifier.collection == "people":
            LOGGER.debug(
                "Render all assets for person %s",
                identifier.collection_id,
            )
            try:
                assets = await immich_api.search.async_get_all_by_person_ids(
                    [identifier.collection_id]
                )
            except ImmichForbiddenError as err:
                raise BrowseError(
                    translation_domain=DOMAIN,
                    translation_key="missing_api_permission",
                    translation_placeholders={"msg": str(err)},
                ) from err
            except ImmichError:
                return []
        elif identifier.collection == "favorites":
            LOGGER.debug("Render all assets for favorites collection")
            try:
                assets = await immich_api.search.async_get_all_favorites()
            except ImmichForbiddenError as err:
                raise BrowseError(
                    translation_domain=DOMAIN,
                    translation_key="missing_api_permission",
                    translation_placeholders={"msg": str(err)},
                ) from err
            except ImmichError:
                return []

        return _parse_assets(assets, identifier)

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        try:
            identifier = ImmichMediaSourceIdentifier(item.identifier)
        except IndexError as err:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="identifier_unresolvable",
                translation_placeholders={"identifier": item.identifier},
            ) from err

        if identifier.mime_type is None:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="identifier_no_mime_type_unresolvable",
                translation_placeholders={"identifier": item.identifier},
            )

        return PlayMedia(
            (
                f"/immich/{identifier.unique_id}/{identifier.asset_id}/fullsize/{identifier.mime_type}"
            ),
            identifier.mime_type,
        )

    @override
    async def async_search_media(
        self, item: MediaSourceItem, query: SearchMediaQuery
    ) -> SearchMedia:
        """Search media."""
        identifier = ImmichMediaSourceIdentifier(item.identifier)
        entry: ImmichConfigEntry | None = (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, identifier.unique_id
            )
        )
        assert entry
        immich_api = entry.runtime_data.api

        search_args: ImmichSmartSearchArgs = {"query": query.search_query}
        if identifier.collection == "albums":
            search_args["is_not_in_album"] = False
            if album_id := identifier.collection_id:
                search_args["album_ids"] = [album_id]

        elif identifier.collection == "people" and (
            person_id := identifier.collection_id
        ):
            search_args["person_ids"] = [person_id]

        elif identifier.collection == "tags" and (tag_id := identifier.collection_id):
            search_args["tag_ids"] = [tag_id]

        elif identifier.collection == "favorites":
            search_args["is_favorite"] = True

        if q_classes := query.media_filter_classes:
            selected_supported_classes = list(
                set(q_classes) & set(MEDIA_CLASS_ASSET_TYPE_MAPPING)
            )
            if len(selected_supported_classes) == 1:
                search_args["asset_type"] = MEDIA_CLASS_ASSET_TYPE_MAPPING[
                    selected_supported_classes[0]
                ]

        try:
            results = await immich_api.search.async_smart_search(**search_args)
        except ImmichForbiddenError as err:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="missing_api_permission",
                translation_placeholders={"msg": str(err)},
            ) from err
        except ImmichError:
            return SearchMedia(result=[])

        return SearchMedia(result=_parse_assets(results, identifier))


class ImmichMediaView(HomeAssistantView):
    """Immich Media Finder View."""

    url = "/immich/{source_dir_id}/{location:.*}"
    name = "immich"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media view."""
        self.hass = hass

    async def get(
        self, request: Request, source_dir_id: str, location: str
    ) -> Response | StreamResponse:
        """Start a GET request."""
        if not self.hass.config_entries.async_loaded_entries(DOMAIN):
            raise HTTPNotFound

        try:
            asset_id, size, mime_type_base, mime_type_format = location.split("/")
        except ValueError as err:
            raise HTTPNotFound from err

        entry: ImmichConfigEntry | None = (
            self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, source_dir_id
            )
        )
        assert entry
        immich_api = entry.runtime_data.api

        # stream response for videos
        if mime_type_base == "video":
            try:
                resp = await immich_api.assets.async_play_video_stream(asset_id)
            except ImmichError as exc:
                raise HTTPNotFound from exc
            stream = ChunkAsyncStreamIterator(resp)
            response = StreamResponse()
            await response.prepare(request)
            async for chunk in stream:
                await response.write(chunk)
            return response

        # web response for images
        try:
            if size == "person":
                image = await immich_api.people.async_get_person_thumbnail(asset_id)
            else:
                image = await immich_api.assets.async_view_asset(asset_id, size)
        except ImmichError as exc:
            raise HTTPNotFound from exc
        return Response(body=image, content_type=f"{mime_type_base}/{mime_type_format}")
