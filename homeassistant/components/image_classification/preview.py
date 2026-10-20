"""Short-lived frame previews for the flows."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
import secrets
from time import monotonic

from aiohttp import web
from PIL import ImageDraw

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import CONF_BOTTOM, CONF_LEFT, CONF_RIGHT, CONF_TOP, DOMAIN
from .frame_source import encode_jpeg, load_image

PREVIEW_URL = f"/api/{DOMAIN}/preview/{{token}}"
PREVIEW_LIFETIME = timedelta(minutes=10)
# Each is a JPEG of up to 1024 px; a flow shows one or two at a time.
MAX_PREVIEWS = 20
DATA_PREVIEWS: HassKey[Previews] = HassKey(f"{DOMAIN}_previews")
OUTLINE = (255, 0, 255)


@dataclass
class Previews:
    """Rendered previews by token."""

    images: dict[str, tuple[float, bytes]] = field(default_factory=dict)

    def purge(self) -> None:
        """Drop expired previews."""
        now = monotonic()
        for token, (created, _) in list(self.images.items()):
            if now - created > PREVIEW_LIFETIME.total_seconds():
                del self.images[token]


def outline(frame: bytes, region: Mapping[str, float] | None) -> bytes:
    """Return the frame as JPEG with a region in percent outlined; blocking."""
    image = load_image(frame)
    if region is not None:
        width, height = image.size
        left = min(round(region[CONF_LEFT] / 100 * width), width - 1)
        top = min(round(region[CONF_TOP] / 100 * height), height - 1)
        right = max(round(region[CONF_RIGHT] / 100 * width), left + 1)
        bottom = max(round(region[CONF_BOTTOM] / 100 * height), top + 1)
        ImageDraw.Draw(image).rectangle(
            (left, top, right - 1, bottom - 1),
            outline=OUTLINE,
            width=max(2, round(max(image.size) / 240)),
        )
    return encode_jpeg(image, quality=85)


async def async_preview_url(
    hass: HomeAssistant, frame: bytes, region: Mapping[str, float] | None
) -> str:
    """Render the frame with the region outlined; return a signed URL to it.

    Raises InvalidFrame when the frame can't be decoded.
    """
    image = await hass.async_add_executor_job(outline, frame, region)
    if (previews := hass.data.get(DATA_PREVIEWS)) is None:
        # The first config flow runs before the integration is set up.
        previews = hass.data[DATA_PREVIEWS] = Previews()
        hass.http.register_view(PreviewView)
    previews.purge()
    while len(previews.images) >= MAX_PREVIEWS:
        del previews.images[next(iter(previews.images))]
    token = secrets.token_hex(16)
    previews.images[token] = (monotonic(), image)
    return async_sign_path(hass, PREVIEW_URL.format(token=token), PREVIEW_LIFETIME)


class PreviewView(HomeAssistantView):
    """Serve previews to the flow dialogs."""

    url = PREVIEW_URL
    name = f"api:{DOMAIN}:preview"

    async def get(self, request: web.Request, token: str) -> web.Response:
        """Return a preview image."""
        previews = request.app[KEY_HASS].data[DATA_PREVIEWS]
        previews.purge()
        if (item := previews.images.get(token)) is None:
            return web.Response(status=404)
        return web.Response(body=item[1], content_type="image/jpeg")
