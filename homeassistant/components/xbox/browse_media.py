"""Support for media browsing."""
from __future__ import annotations

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.catalog.const import HOME_APP_IDS, SYSTEM_PFN_ID_MAP
from xbox.webapi.api.provider.catalog.models import (
    AlternateIdType,
    CatalogResponse,
    FieldsTemplate,
    Image,
)
from xbox.webapi.api.provider.smartglass.models import (
    InstalledPackage,
    InstalledPackagesList,
)

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_APP,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_GAME,
    MEDIA_TYPE_APP,
    MEDIA_TYPE_GAME,
)

TYPE_MAP = {
    "App": {
        "type": MEDIA_TYPE_APP,
        "class": MEDIA_CLASS_APP,
    },
    "Game": {
        "type": MEDIA_TYPE_GAME,
        "class": MEDIA_CLASS_GAME,
    },
}


async def build_item_response(
    client: XboxLiveClient,
    device_id: str,
    tv_configured: bool,
    media_content_type: str,
    media_content_id: str,
) -> BrowseMedia | None:
    """Create response payload for the provided media query."""
    apps: InstalledPackagesList = await client.smartglass.get_installed_apps(device_id)

    if media_content_type in [None, "library"]:
        library_info = BrowseMedia(
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_id="library",
            media_content_type="library",
            title="Installed Applications",
            can_play=False,
            can_expand=True,
            children=[],
        )

        # Add Home
        id_type = AlternateIdType.LEGACY_XBOX_PRODUCT_ID
        home_catalog: CatalogResponse = (
            await client.catalog.get_product_from_alternate_id(
                HOME_APP_IDS[id_type], id_type
            )
        )
        home_thumb = _find_media_image(
            home_catalog.products[0].localized_properties[0].images
        )
        library_info.children.append(
            BrowseMedia(
                media_class=MEDIA_CLASS_APP,
                media_content_id="Home",
                media_content_type=MEDIA_TYPE_APP,
                title="Home",
                can_play=True,
                can_expand=False,
                thumbnail=home_thumb.uri,
            )
        )

        # Add TV if configured
        if tv_configured:
            tv_catalog: CatalogResponse = (
                await client.catalog.get_product_from_alternate_id(
                    SYSTEM_PFN_ID_MAP["Microsoft.Xbox.LiveTV_8wekyb3d8bbwe"][id_type],
                    id_type,
                )
            )
            tv_thumb = _find_media_image(
                tv_catalog.products[0].localized_properties[0].images
            )
            library_info.children.append(
                BrowseMedia(
                    media_class=MEDIA_CLASS_APP,
                    media_content_id="TV",
                    media_content_type=MEDIA_TYPE_APP,
                    title="Live TV",
                    can_play=True,
                    can_expand=False,
                    thumbnail=tv_thumb.uri,
                )
            )

        content_types = sorted(
            {app.content_type for app in apps.result if app.content_type in TYPE_MAP}
        )
        for c_type in content_types:
            library_info.children.append(
                BrowseMedia(
                    media_class=MEDIA_CLASS_DIRECTORY,
                    media_content_id=c_type,
                    media_content_type=TYPE_MAP[c_type]["type"],
                    title=f"{c_type}s",
                    can_play=False,
                    can_expand=True,
                    children_media_class=TYPE_MAP[c_type]["class"],
                )
            )

        return library_info

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
        media_class=MEDIA_CLASS_DIRECTORY,
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
        children_media_class=TYPE_MAP[media_content_id]["class"],
    )


def item_payload(item: InstalledPackage, images: dict[str, list[Image]]):
    """Create response payload for a single media item."""
    thumbnail = None
    image = _find_media_image(images.get(item.one_store_product_id, []))
    if image is not None:
        thumbnail = image.uri
        if thumbnail[0] == "/":
            thumbnail = f"https:{thumbnail}"

    return BrowseMedia(
        media_class=TYPE_MAP[item.content_type]["class"],
        media_content_id=item.one_store_product_id,
        media_content_type=TYPE_MAP[item.content_type]["type"],
        title=item.name,
        can_play=True,
        can_expand=False,
        thumbnail=thumbnail,
    )


def _find_media_image(images: list[Image]) -> Image | None:
    purpose_order = ["Poster", "Tile", "Logo", "BoxArt"]
    for purpose in purpose_order:
        for image in images:
            if image.image_purpose == purpose and image.width >= 300:
                return image
    return None
