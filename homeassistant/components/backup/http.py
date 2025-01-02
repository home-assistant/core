"""Http view for the Backup integration."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import cast

from aiohttp import BodyPartReader
from aiohttp.hdrs import CONTENT_DISPOSITION
from aiohttp.web import FileResponse, Request, Response, StreamResponse

from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from .const import DATA_MANAGER


@callback
def async_register_http_views(hass: HomeAssistant) -> None:
    """Register the http views."""
    hass.http.register_view(DownloadBackupView)
    hass.http.register_view(UploadBackupView)


class DownloadBackupView(HomeAssistantView):
    """Generate backup view."""

    url = "/api/backup/download/{backup_id}"
    name = "api:backup:download"

    async def get(
        self,
        request: Request,
        backup_id: str,
    ) -> StreamResponse | FileResponse | Response:
        """Download a backup file."""
        if not request["hass_user"].is_admin:
            return Response(status=HTTPStatus.UNAUTHORIZED)
        try:
            agent_id = request.query.getone("agent_id")
        except KeyError:
            return Response(status=HTTPStatus.BAD_REQUEST)

        manager = request.app[KEY_HASS].data[DATA_MANAGER]
        if agent_id not in manager.backup_agents:
            return Response(status=HTTPStatus.BAD_REQUEST)
        agent = manager.backup_agents[agent_id]
        backup = await agent.async_get_backup(backup_id)

        # We don't need to check if the path exists, aiohttp.FileResponse will handle
        # that
        if backup is None:
            return Response(status=HTTPStatus.NOT_FOUND)

        headers = {
            CONTENT_DISPOSITION: f"attachment; filename={slugify(backup.name)}.tar"
        }
        if agent_id in manager.local_backup_agents:
            local_agent = manager.local_backup_agents[agent_id]
            path = local_agent.get_backup_path(backup_id)
            return FileResponse(path=path.as_posix(), headers=headers)

        stream = await agent.async_download_backup(backup_id)
        response = StreamResponse(status=HTTPStatus.OK, headers=headers)
        await response.prepare(request)
        async for chunk in stream:
            await response.write(chunk)
        return response


class UploadBackupView(HomeAssistantView):
    """Generate backup view."""

    url = "/api/backup/upload"
    name = "api:backup:upload"

    @require_admin
    async def post(self, request: Request) -> Response:
        """Upload a backup file."""
        try:
            agent_ids = request.query.getall("agent_id")
        except KeyError:
            return Response(status=HTTPStatus.BAD_REQUEST)
        manager = request.app[KEY_HASS].data[DATA_MANAGER]
        reader = await request.multipart()
        contents = cast(BodyPartReader, await reader.next())

        try:
            await manager.async_receive_backup(contents=contents, agent_ids=agent_ids)
        except OSError as err:
            return Response(
                body=f"Can't write backup file: {err}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except HomeAssistantError as err:
            return Response(
                body=f"Can't upload backup file: {err}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        except asyncio.CancelledError:
            return Response(status=HTTPStatus.INTERNAL_SERVER_ERROR)

        return Response(status=HTTPStatus.CREATED)
