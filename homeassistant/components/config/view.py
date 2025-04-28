"""Component to configure Home Assistant via an API."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from http import HTTPStatus
import os
from typing import Any, cast

from aiohttp import web
import voluptuous as vol

from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.file import write_utf8_file_atomic
from homeassistant.util.yaml import dump, load_yaml
from homeassistant.util.yaml.loader import JSON_TYPE

from .const import ACTION_CREATE_UPDATE, ACTION_DELETE


class BaseEditConfigView[_DataT: (dict[str, dict[str, Any]], list[dict[str, Any]])](
    HomeAssistantView
):
    """Configure a Group endpoint."""

    def __init__(
        self,
        component: str,
        config_type: str,
        path: str,
        key_schema: Callable[[Any], str],
        *,
        post_write_hook: Callable[[str, str], Coroutine[Any, Any, None]] | None = None,
        data_schema: Callable[[dict[str, Any]], Any] | None = None,
        data_validator: Callable[
            [HomeAssistant, str, dict[str, Any]],
            Coroutine[Any, Any, dict[str, Any] | None],
        ]
        | None = None,
    ) -> None:
        """Initialize a config view."""
        self.url = f"/api/config/{component}/{config_type}/{{config_key}}"
        self.name = f"api:config:{component}:{config_type}"
        self.path = path
        self.key_schema = key_schema
        self.data_schema = data_schema
        self.post_write_hook = post_write_hook
        self.data_validator = data_validator
        self.mutation_lock = asyncio.Lock()
        if (self.data_schema is None and self.data_validator is None) or (
            self.data_schema is not None and self.data_validator is not None
        ):
            raise ValueError(
                "Must specify exactly one of data_schema or data_validator"
            )

    def _empty_config(self) -> _DataT:
        """Empty config if file not found."""
        raise NotImplementedError

    def _get_value(
        self, hass: HomeAssistant, data: _DataT, config_key: str
    ) -> dict[str, Any] | None:
        """Get value."""
        raise NotImplementedError

    def _write_value(
        self,
        hass: HomeAssistant,
        data: _DataT,
        config_key: str,
        new_value: dict[str, Any],
    ) -> None:
        """Set value."""
        raise NotImplementedError

    def _delete_value(
        self, hass: HomeAssistant, data: _DataT, config_key: str
    ) -> dict[str, Any] | None:
        """Delete value."""
        raise NotImplementedError

    @require_admin
    async def get(self, request: web.Request, config_key: str) -> web.Response:
        """Fetch device specific config."""
        hass = request.app[KEY_HASS]
        async with self.mutation_lock:
            current = await self.read_config(hass)
            value = self._get_value(hass, current, config_key)

        if value is None:
            return self.json_message("Resource not found", HTTPStatus.NOT_FOUND)

        return self.json(value)

    @require_admin
    async def post(self, request: web.Request, config_key: str) -> web.Response:
        """Validate config and return results."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON specified", HTTPStatus.BAD_REQUEST)

        try:
            self.key_schema(config_key)
        except vol.Invalid as err:
            return self.json_message(f"Key malformed: {err}", HTTPStatus.BAD_REQUEST)

        hass = request.app[KEY_HASS]

        try:
            # We just validate, we don't store that data because
            # we don't want to store the defaults.
            if self.data_validator:
                await self.data_validator(hass, config_key, data)
            else:
                # We either have a data_schema or a data_validator, ignore mypy
                self.data_schema(data)  # type: ignore[misc]
        except (vol.Invalid, HomeAssistantError) as err:
            return self.json_message(
                f"Message malformed: {err}", HTTPStatus.BAD_REQUEST
            )

        path = hass.config.path(self.path)

        async with self.mutation_lock:
            current = await self.read_config(hass)
            self._write_value(hass, current, config_key, data)

            await hass.async_add_executor_job(_write, path, current)

        if self.post_write_hook is not None:
            hass.async_create_task(
                self.post_write_hook(ACTION_CREATE_UPDATE, config_key)
            )

        return self.json({"result": "ok"})

    @require_admin
    async def delete(self, request: web.Request, config_key: str) -> web.Response:
        """Remove an entry."""
        hass = request.app[KEY_HASS]
        async with self.mutation_lock:
            current = await self.read_config(hass)
            value = self._get_value(hass, current, config_key)
            path = hass.config.path(self.path)

            if value is None:
                return self.json_message("Resource not found", HTTPStatus.BAD_REQUEST)

            self._delete_value(hass, current, config_key)
            await hass.async_add_executor_job(_write, path, current)

        if self.post_write_hook is not None:
            hass.async_create_task(self.post_write_hook(ACTION_DELETE, config_key))

        return self.json({"result": "ok"})

    async def read_config(self, hass: HomeAssistant) -> _DataT:
        """Read the config."""
        current = await hass.async_add_executor_job(_read, hass.config.path(self.path))
        if not current:
            current = self._empty_config()
        return cast(_DataT, current)


class EditKeyBasedConfigView(BaseEditConfigView[dict[str, dict[str, Any]]]):
    """Configure a list of entries."""

    def _empty_config(self) -> dict[str, Any]:
        """Return an empty config."""
        return {}

    def _get_value(
        self, hass: HomeAssistant, data: dict[str, dict[str, Any]], config_key: str
    ) -> dict[str, Any] | None:
        """Get value."""
        return data.get(config_key)

    def _write_value(
        self,
        hass: HomeAssistant,
        data: dict[str, dict[str, Any]],
        config_key: str,
        new_value: dict[str, Any],
    ) -> None:
        """Set value."""
        data.setdefault(config_key, {}).update(new_value)

    def _delete_value(
        self, hass: HomeAssistant, data: dict[str, dict[str, Any]], config_key: str
    ) -> dict[str, Any]:
        """Delete value."""
        return data.pop(config_key)


class EditIdBasedConfigView(BaseEditConfigView[list[dict[str, Any]]]):
    """Configure key based config entries."""

    def _empty_config(self) -> list[Any]:
        """Return an empty config."""
        return []

    def _get_value(
        self, hass: HomeAssistant, data: list[dict[str, Any]], config_key: str
    ) -> dict[str, Any] | None:
        """Get value."""
        return next((val for val in data if val.get(CONF_ID) == config_key), None)

    def _write_value(
        self,
        hass: HomeAssistant,
        data: list[dict[str, Any]],
        config_key: str,
        new_value: dict[str, Any],
    ) -> None:
        """Set value."""
        if (value := self._get_value(hass, data, config_key)) is None:
            value = {CONF_ID: config_key}
            data.append(value)

        value.update(new_value)

    def _delete_value(
        self, hass: HomeAssistant, data: list[dict[str, Any]], config_key: str
    ) -> None:
        """Delete value."""
        index = next(
            idx for idx, val in enumerate(data) if val.get(CONF_ID) == config_key
        )
        data.pop(index)


def _read(path: str) -> JSON_TYPE | None:
    """Read YAML helper."""
    if not os.path.isfile(path):
        return None

    return load_yaml(path)


def _write(path: str, data: dict | list) -> None:
    """Write YAML helper."""
    # Do it before opening file. If dump causes error it will now not
    # truncate the file.
    contents = dump(data)
    write_utf8_file_atomic(path, contents)
