"""Http view for the Backup integration."""

from __future__ import annotations

import asyncio
from http import HTTPStatus
import threading
from typing import IO, cast

from aiohttp import BodyPartReader
from aiohttp.hdrs import CONTENT_DISPOSITION
from aiohttp.web import FileResponse, Request, Response, StreamResponse
from multidict import istr

from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import util
from .agent import BackupAgent
from .const import DATA_MANAGER
from .manager import BackupManager


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
        try:
            password = request.query.getone("password")
        except KeyError:
            password = None

        hass = request.app[KEY_HASS]
        manager = hass.data[DATA_MANAGER]
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

        if not password:
            return await self._send_backup_no_password(
                request, headers, backup_id, agent_id, agent, manager
            )
        return await self._send_backup_with_password(
            hass, request, headers, backup_id, agent_id, password, agent, manager
        )

    async def _send_backup_no_password(
        self,
        request: Request,
        headers: dict[istr, str],
        backup_id: str,
        agent_id: str,
        agent: BackupAgent,
        manager: BackupManager,
    ) -> StreamResponse | FileResponse | Response:
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

    async def _send_backup_with_password(
        self,
        hass: HomeAssistant,
        request: Request,
        headers: dict[istr, str],
        backup_id: str,
        agent_id: str,
        password: str,
        agent: BackupAgent,
        manager: BackupManager,
    ) -> StreamResponse | FileResponse | Response:
        reader: IO[bytes]
        if agent_id in manager.local_backup_agents:
            local_agent = manager.local_backup_agents[agent_id]
            path = local_agent.get_backup_path(backup_id)
            try:
                reader = await hass.async_add_executor_job(open, path.as_posix(), "rb")
            except FileNotFoundError:
                return Response(status=HTTPStatus.NOT_FOUND)
        else:
            stream = await agent.async_download_backup(backup_id)
            reader = cast(IO[bytes], util.AsyncIteratorReader(hass, stream))

        worker_done_event = asyncio.Event()

        def on_done() -> None:
            """Call by the worker thread when it's done."""
            hass.loop.call_soon_threadsafe(worker_done_event.set)

        stream = util.AsyncIteratorWriter(hass)
        worker = threading.Thread(
            target=util.decrypt_backup, args=[reader, stream, password, on_done]
        )
        try:
            worker.start()
            response = StreamResponse(status=HTTPStatus.OK, headers=headers)
            await response.prepare(request)
            async for chunk in stream:
                await response.write(chunk)
            return response
        finally:
            reader.close()
            await worker_done_event.wait()


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
