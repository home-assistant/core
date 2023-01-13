"""Component to configure Home Assistant via an API."""
import asyncio
from http import HTTPStatus
import importlib
import os

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_ID, EVENT_COMPONENT_LOADED
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import ATTR_COMPONENT
from homeassistant.util.file import write_utf8_file_atomic
from homeassistant.util.yaml import dump, load_yaml

DOMAIN = "config"
SECTIONS = (
    "area_registry",
    "auth",
    "auth_provider_homeassistant",
    "automation",
    "config_entries",
    "core",
    "device_registry",
    "entity_registry",
    "script",
    "scene",
)
ACTION_CREATE_UPDATE = "create_update"
ACTION_DELETE = "delete"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the config component."""
    frontend.async_register_built_in_panel(
        hass, "config", "config", "hass:cog", require_admin=True
    )

    async def setup_panel(panel_name):
        """Set up a panel."""
        panel = importlib.import_module(f".{panel_name}", __name__)

        if not panel:
            return

        success = await panel.async_setup(hass)

        if success:
            key = f"{DOMAIN}.{panel_name}"
            hass.bus.async_fire(EVENT_COMPONENT_LOADED, {ATTR_COMPONENT: key})

    tasks = [asyncio.create_task(setup_panel(panel_name)) for panel_name in SECTIONS]

    if tasks:
        await asyncio.wait(tasks)

    return True


class BaseEditConfigView(HomeAssistantView):
    """Configure a Group endpoint."""

    def __init__(
        self,
        component,
        config_type,
        path,
        key_schema,
        data_schema,
        *,
        post_write_hook=None,
        data_validator=None,
    ):
        """Initialize a config view."""
        self.url = f"/api/config/{component}/{config_type}/{{config_key}}"
        self.name = f"api:config:{component}:{config_type}"
        self.path = path
        self.key_schema = key_schema
        self.data_schema = data_schema
        self.post_write_hook = post_write_hook
        self.data_validator = data_validator
        self.mutation_lock = asyncio.Lock()

    def _empty_config(self):
        """Empty config if file not found."""
        raise NotImplementedError

    def _get_value(self, hass, data, config_key):
        """Get value."""
        raise NotImplementedError

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        raise NotImplementedError

    def _delete_value(self, hass, data, config_key):
        """Delete value."""
        raise NotImplementedError

    async def get(self, request, config_key):
        """Fetch device specific config."""
        hass = request.app["hass"]
        async with self.mutation_lock:
            current = await self.read_config(hass)
            value = self._get_value(hass, current, config_key)

        if value is None:
            return self.json_message("Resource not found", HTTPStatus.NOT_FOUND)

        return self.json(value)

    async def post(self, request, config_key):
        """Validate config and return results."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON specified", HTTPStatus.BAD_REQUEST)

        try:
            self.key_schema(config_key)
        except vol.Invalid as err:
            return self.json_message(f"Key malformed: {err}", HTTPStatus.BAD_REQUEST)

        hass = request.app["hass"]

        try:
            # We just validate, we don't store that data because
            # we don't want to store the defaults.
            if self.data_validator:
                await self.data_validator(hass, config_key, data)
            else:
                self.data_schema(data)
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

    async def delete(self, request, config_key):
        """Remove an entry."""
        hass = request.app["hass"]
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

    async def read_config(self, hass):
        """Read the config."""
        current = await hass.async_add_executor_job(_read, hass.config.path(self.path))
        if not current:
            current = self._empty_config()
        return current


class EditKeyBasedConfigView(BaseEditConfigView):
    """Configure a list of entries."""

    def _empty_config(self):
        """Return an empty config."""
        return {}

    def _get_value(self, hass, data, config_key):
        """Get value."""
        return data.get(config_key)

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        data.setdefault(config_key, {}).update(new_value)

    def _delete_value(self, hass, data, config_key):
        """Delete value."""
        return data.pop(config_key)


class EditIdBasedConfigView(BaseEditConfigView):
    """Configure key based config entries."""

    def _empty_config(self):
        """Return an empty config."""
        return []

    def _get_value(self, hass, data, config_key):
        """Get value."""
        return next((val for val in data if val.get(CONF_ID) == config_key), None)

    def _write_value(self, hass, data, config_key, new_value):
        """Set value."""
        if (value := self._get_value(hass, data, config_key)) is None:
            value = {CONF_ID: config_key}
            data.append(value)

        value.update(new_value)

    def _delete_value(self, hass, data, config_key):
        """Delete value."""
        index = next(
            idx for idx, val in enumerate(data) if val.get(CONF_ID) == config_key
        )
        data.pop(index)


def _read(path):
    """Read YAML helper."""
    if not os.path.isfile(path):
        return None

    return load_yaml(path)


def _write(path, data):
    """Write YAML helper."""
    # Do it before opening file. If dump causes error it will now not
    # truncate the file.
    contents = dump(data)
    write_utf8_file_atomic(path, contents)
