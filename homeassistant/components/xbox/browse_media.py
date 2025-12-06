"""Support for media browsing."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from pythonxbox.api.client import XboxLiveClient
from pythonxbox.api.provider.catalog.const import HOME_APP_IDS
from pythonxbox.api.provider.catalog.models import (
    AlternateIdType,
    CatalogResponse,
    FieldsTemplate,
    Image,
)
from pythonxbox.api.provider.smartglass.models import (
    InstalledPackage,
    InstalledPackagesList,
)

from homeassistant.components.media_player import BrowseMedia, MediaClass, MediaType

from .entity import to_https


class MediaTypeDetails(NamedTuple):
    """Details for media type."""

    type: str
    cls: str


TYPE_MAP = {
    "App": MediaTypeDetails(
        type=MediaType.APP,
        cls=MediaClass.APP,
    ),
    "Game": MediaTypeDetails(
        type=MediaType.GAME,
        cls=MediaClass.GAME,
    ),
}


async def build_item_response(
    client: XboxLiveClient,
    device_id: str,
    media_content_type: MediaType | str | None = None,
    media_content_id: str | None = None,
) -> BrowseMedia:
    """Create response payload for the provided media query."""
    apps: InstalledPackagesList = await client.smartglass.get_installed_apps(device_id)

    if media_content_type is not None and media_content_id is not None:
        app_details = await client.catalog.get_products(
            [
                app.one_store_product_id
                for app in apps.result
                if app.content_type == media_content_id and app.one_store_product_id
            ],
            FieldsTemplate.BROWSE,
        )

        images = {
            prod.product_id: prod.localized_properties[0].images
            for prod in app_details.products
        }

        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=media_content_id,
            media_content_type=media_content_type,
            title=f"{media_content_id}s",
            can_play=False,
            can_expand=True,
            children=[
                item_payload(app, images)
                for app in apps.result
                if app.content_type == media_content_id and app.one_store_product_id
            ],
            children_media_class=TYPE_MAP[media_content_id].cls,
        )

    children: list[BrowseMedia] = []
    library_info = BrowseMedia(
        media_class=MediaClass.DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        title="Installed Applications",
        can_play=False,
        can_expand=True,
        children=children,
    )

    # Add Home
    id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
    home_catalog: CatalogResponse = await client.catalog.get_product_from_alternate_id(
        HOME_APP_IDS[id_type], id_type
    )
    home_thumb = _find_media_image(
        home_catalog.products[0].localized_properties[0].images
    )
    children.append(
        BrowseMedia(
            media_class=MediaClass.APP,
            media_content_id="Home",
            media_content_type=MediaType.APP,
            title="Home",
            can_play=True,
            can_expand=False,
            thumbnail=home_thumb,
        )
    )

    content_types = sorted(
        {app.content_type for app in apps.result if app.content_type in TYPE_MAP}
    )
    children.extend(
        BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=c_type,
            media_content_type=TYPE_MAP[c_type].type,
            title=f"{c_type}s",
            can_play=False,
            can_expand=True,
            children_media_class=TYPE_MAP[c_type].cls,
        )
        for c_type in content_types
    )

    return library_info


def item_payload(item: InstalledPackage, images: dict[str, list[Image]]) -> BrowseMedia:
    """Create response payload for a single media item."""
    if TYPE_CHECKING:
        assert item.one_store_product_id
        assert item.name

    return BrowseMedia(
        media_class=TYPE_MAP[item.content_type].cls,
        media_content_id=item.one_store_product_id,
        media_content_type=TYPE_MAP[item.content_type].type,
        title=item.name,
        can_play=True,
        can_expand=False,
        thumbnail=_find_media_image(images.get(item.one_store_product_id, [])),
    )


def _find_media_image(images: list[Image]) -> str | None:
    purpose_order = ["BrandedKeyArt", "Poster", "BoxArt", "Tile"]
    for purpose in purpose_order:
        if match := next(
            (image for image in images if image.image_purpose == purpose), None
        ):
            return to_https(match.uri)
    return None
