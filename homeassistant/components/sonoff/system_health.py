"""Provide info to system health."""
import logging
import re
import traceback
import uuid
from collections import deque
from datetime import datetime
from logging import Logger
from typing import Any

from aiohttp import web
from homeassistant.components import system_health
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback

from .core.const import DOMAIN, PRIVATE_KEYS, source_hash


@callback
def async_register(
        hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant):
    cloud_online = local_online = cloud_total = local_total = 0

    for registry in hass.data[DOMAIN].values():
        for device in registry.devices.values():
            if "online" in device:
                cloud_total += 1
                if registry.cloud.online and device["online"]:
                    cloud_online += 1
            # localtype - all discovered local devices
            # host - all online local devices (maybe encrypted)
            # params - all local unencrypted devices
            if "localtype" in device:
                local_total += 1
                if "host" in device and "params" in device:
                    local_online += 1

    integration = hass.data["integrations"][DOMAIN]
    info = {
        "version": f"{integration.version} ({source_hash()})",
        "cloud_online": f"{cloud_online} / {cloud_total}",
        "local_online": f"{local_online} / {local_total}",
    }

    if DebugView.url:
        info["debug"] = {
            "type": "failed", "error": "", "more_info": DebugView.url
        }

    return info


async def setup_debug(hass: HomeAssistant, logger: Logger):
    view = DebugView(logger)
    hass.http.register_view(view)

    integration = hass.data["integrations"][DOMAIN]
    info = await hass.helpers.system_info.async_get_system_info()
    info[DOMAIN + "_version"] = f"{integration.version} ({source_hash()})"
    logger.debug(f"SysInfo: {info}")


class DebugView(logging.Handler, HomeAssistantView):
    """Class generate web page with component debug logs."""
    name = DOMAIN
    requires_auth = False

    def __init__(self, logger: Logger):
        super().__init__()

        # https://waymoot.org/home/python_string/
        self.text = deque(maxlen=10000)

        self.propagate_level = logger.getEffectiveLevel()

        # random url because without authorization!!!
        DebugView.url = f"/api/{DOMAIN}/{uuid.uuid4()}"

        logger.addHandler(self)
        logger.setLevel(logging.DEBUG)

    def handle(self, rec: logging.LogRecord):
        if isinstance(rec.args, dict):
            rec.msg = rec.msg % {
                k: v for k, v in rec.args.items() if k not in PRIVATE_KEYS
            }
        dt = datetime.fromtimestamp(rec.created).strftime("%Y-%m-%d %H:%M:%S")
        msg = f"{dt} [{rec.levelname[0]}] {rec.msg}"
        if rec.exc_info:
            exc = traceback.format_exception(*rec.exc_info, limit=1)
            msg += "|" + "".join(exc[-2:]).replace("\n", "|")
        self.text.append(msg)

        # prevent debug to Hass log if user don't want it
        if self.propagate_level > rec.levelno:
            rec.levelno = -1

    async def get(self, request: web.Request):
        try:
            lines = self.text

            if 'q' in request.query:
                reg = re.compile(fr"({request.query['q']})", re.IGNORECASE)
                lines = [p for p in lines if reg.search(p)]

            if 't' in request.query:
                tail = int(request.query['t'])
                lines = lines[-tail:]

            body = "\n".join(lines)
            r = request.query.get('r', '')

            return web.Response(
                text='<!DOCTYPE html><html>'
                     f'<head><meta http-equiv="refresh" content="{r}"></head>'
                     f'<body><pre>{body}</pre></body>'
                     '</html>',
                content_type="text/html"
            )
        except Exception:
            return web.Response(status=500)
