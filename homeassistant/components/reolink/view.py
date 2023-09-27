"""Implement a view to provide extra camera functionality."""

from __future__ import annotations

from typing import Any

from aiohttp import web

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN, Camera, CameraView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

from . import camera as camera_module


# would like a cleaner way to do this
def _async_get_camera_component(hass: HomeAssistant) -> EntityComponent[Camera]:
    return hass.data[CAMERA_DOMAIN]


def async_setup_views(hass: HomeAssistant):
    """Register camera views with http provider."""

    component = _async_get_camera_component(hass)
    hass.http.register_view(ReoLinkCameraDownloadView(component))


class ReolinkCameraView(CameraView):
    """Base Reolink Camera View."""

    async def get(
        self, request: web.Request, entity_id: str, *args, **kwargs: Any
    ) -> web.StreamResponse:
        """Get method."""
        request["get_args"] = args
        request["get_kwargs"] = kwargs
        return await super().get(request, entity_id)

    async def handle(self, request: web.Request, camera: Camera) -> web.StreamResponse:
        """Handle the camera request."""
        if not isinstance(camera, camera_module.ReolinkCamera):
            raise web.HTTPBadRequest()

        return await self._handle_reolink(
            request,
            camera,
            *request.get("get_args", ()),
            **request.get("get_kwargs", {}),
        )

    async def _handle_reolink(
        self,
        request: web.Request,
        camera: camera_module.ReolinkCamera,
        *args: Any,
        **kwargs: Any,
    ) -> web.StreamResponse:
        """Handle the camera request."""
        raise NotImplementedError()


class ReoLinkCameraDownloadView(ReolinkCameraView):
    """Download viewer to handle camera recordings."""

    url = "/api/reolink_download/{entity_id}/{filename:.*}"
    name = "api:reolink:download"

    async def _handle_reolink(
        self,
        request: web.Request,
        camera: camera_module.ReolinkCamera,
        *args: Any,
        filename: str | None = None,
        **kwargs: Any,
    ) -> web.StreamResponse:
        """Serve camera stream, possibly with interval."""

        # pylint: disable=fixme
        # TODO : validate/sanitize/verify filename to minimize possible attacks

        if not isinstance(filename, str):
            raise web.HTTPBadRequest()

        return await camera.handle_async_download_stream(filename)
