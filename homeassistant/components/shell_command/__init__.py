"""Expose regular shell commands as services."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from contextlib import suppress
import logging
import shlex
from typing import Any

import voluptuous as vol

import homeassistant.config as conf_util
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import (
    config_validation as cv,
    issue_registry as ir,
    service as service_helper,
    template,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.json import JsonObjectType

DOMAIN = "shell_command"

COMMAND_TIMEOUT = 60

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(cv.string)}, extra=vol.ALLOW_EXTRA
)


def _make_handler(
    cmd: str,
    hass: HomeAssistant,
    cache: dict[str, tuple[str, str | None, template.Template | None]],
) -> Callable[[ServiceCall], Coroutine[Any, Any, ServiceResponse]]:
    """Return a service handler that executes the given shell command."""

    async def async_service_handler(service: ServiceCall) -> ServiceResponse:
        if cmd in cache:
            prog, args, args_compiled = cache[cmd]
        elif " " not in cmd:
            prog = cmd
            args = None
            args_compiled = None
            cache[cmd] = prog, args, args_compiled
        else:
            prog, args = cmd.split(" ", 1)
            args_compiled = template.Template(str(args), hass)
            cache[cmd] = prog, args, args_compiled

        if args_compiled:
            try:
                rendered_args = args_compiled.async_render(
                    variables=service.data, parse_result=False
                )
            except TemplateError:
                _LOGGER.exception("Error rendering command template")
                raise
        else:
            rendered_args = None

        if rendered_args == args:
            # No template used. default behavior
            create_process = asyncio.create_subprocess_shell(
                cmd,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                close_fds=False,  # required for posix_spawn
            )
        else:
            # Template used. Break into list and use create_subprocess_exec
            # (which uses shell=False) for security
            shlexed_cmd = [prog, *shlex.split(rendered_args)]
            create_process = asyncio.create_subprocess_exec(
                *shlexed_cmd,
                stdin=None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                close_fds=False,  # required for posix_spawn
            )

        process = await create_process
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT):
                stdout_data, stderr_data = await process.communicate()
        except TimeoutError as err:
            _LOGGER.error(
                "Timed out running command: `%s`, after: %ss", cmd, COMMAND_TIMEOUT
            )
            if process:
                with suppress(TypeError):
                    process.kill()
                    # https://bugs.python.org/issue43884
                    process._transport.close()  # type: ignore[attr-defined]  # noqa: SLF001
                del process

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout",
                translation_placeholders={
                    "command": cmd,
                    "timeout": str(COMMAND_TIMEOUT),
                },
            ) from err

        if stdout_data:
            _LOGGER.debug(
                "Stdout of command: `%s`, return code: %s:\n%s",
                cmd,
                process.returncode,
                stdout_data,
            )
        if stderr_data:
            _LOGGER.debug(
                "Stderr of command: `%s`, return code: %s:\n%s",
                cmd,
                process.returncode,
                stderr_data,
            )
        if process.returncode != 0:
            _LOGGER.exception(
                "Error running command: `%s`, return code: %s", cmd, process.returncode
            )

        if service.return_response:
            service_response: JsonObjectType = {
                "stdout": "",
                "stderr": "",
                "returncode": process.returncode,
            }
            try:
                if stdout_data:
                    service_response["stdout"] = stdout_data.decode("utf-8").strip()
                if stderr_data:
                    service_response["stderr"] = stderr_data.decode("utf-8").strip()
            except UnicodeDecodeError as err:
                _LOGGER.exception(
                    "Unable to handle non-utf8 output of command: `%s`", cmd
                )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="non_utf8_output",
                    translation_placeholders={"command": cmd},
                ) from err
            return service_response
        return None

    return async_service_handler


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the shell_command component."""
    conf = config.get(DOMAIN, {})

    cache: dict[str, tuple[str, str | None, template.Template | None]] = {}

    for name, command in conf.items():
        if name == SERVICE_RELOAD:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"reserved_{SERVICE_RELOAD}",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="reserved_reload_name",
                translation_placeholders={"name": name},
            )
            _LOGGER.warning("Skipping shell_command entry '%s': name is reserved", name)
            continue
        hass.services.async_register(
            DOMAIN,
            name,
            _make_handler(command, hass, cache),
            supports_response=SupportsResponse.OPTIONAL,
        )

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload shell_command from YAML configuration."""
        try:
            raw_config = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error("Error loading configuration.yaml: %s", err)
            return

        try:
            new_conf = CONFIG_SCHEMA(raw_config).get(DOMAIN, {})
        except vol.Invalid as err:
            _LOGGER.error("Invalid shell_command configuration: %s", err)
            return

        for svc in list(hass.services.async_services_for_domain(DOMAIN)):
            if svc != SERVICE_RELOAD:
                hass.services.async_remove(DOMAIN, svc)
        cache.clear()
        ir.async_delete_issue(hass, DOMAIN, f"reserved_{SERVICE_RELOAD}")
        for name, command in new_conf.items():
            if name == SERVICE_RELOAD:
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    f"reserved_{SERVICE_RELOAD}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="reserved_reload_name",
                    translation_placeholders={"name": name},
                )
                _LOGGER.warning(
                    "Skipping shell_command entry '%s': name is reserved", name
                )
                continue
            hass.services.async_register(
                DOMAIN,
                name,
                _make_handler(command, hass, cache),
                supports_response=SupportsResponse.OPTIONAL,
            )

    service_helper.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
    )

    return True
