"""Component to configure Home Assistant via an API."""
import asyncio
import importlib
import os

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    CONF_ID,
    EVENT_COMPONENT_LOADED,
    HTTP_BAD_REQUEST,
    HTTP_NOT_FOUND,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import ATTR_COMPONENT
from homeassistant.util.yaml import dump, load_yaml

DOMAIN = "config"
SECTIONS = (
    "area_registry",
    "auth",
    "auth_provider_homeassistant",
    "automation",
    "config_entries",
    "core",
    "customize",
    "device_registry",
    "entity_registry",
    "group",
    "script",
    "scene",
)
ON_DEMAND = ("zwave",)
ACTION_CREATE_UPDATE = "create_update"
ACTION_DELETE = "delete"


async def async_setup(hass, config):
    """Set up the config component."""
    hass.components.frontend.async_register_built_in_panel(
        "config", "config", "hass:cog", require_admin=True
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

    @callback
    def component_loaded(event):
        """Respond to components being loaded."""
        panel_name = event.data.get(ATTR_COMPONENT)
        if panel_name in ON_DEMAND:
            hass.async_create_task(setup_panel(panel_name))

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, component_loaded)

    tasks = [setup_panel(panel_name) for panel_name in SECTIONS]

    for panel_name in ON_DEMAND:
        if panel_name in hass.config.components:
            tasks.append(setup_panel(panel_name))

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
            return self.json_message("Resource not found", HTTP_NOT_FOUND)

        return self.json(value)

    async def post(self, request, config_key):
        """Validate config and return results."""
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON specified", HTTP_BAD_REQUEST)

        try:
            self.key_schema(config_key)
        except vol.Invalid as err:
            return self.json_message(f"Key malformed: {err}", HTTP_BAD_REQUEST)

        hass = request.app["hass"]

        try:
            # We just validate, we don't store that data because
            # we don't want to store the defaults.
            if self.data_validator:
                await self.data_validator(hass, data)
            else:
                self.data_schema(data)
        except (vol.Invalid, HomeAssistantError) as err:
            return self.json_message(f"Message malformed: {err}", HTTP_BAD_REQUEST)

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
                return self.json_message("Resource not found", HTTP_NOT_FOUND)

            self._delete_value(hass, current, config_key)
            await hass.async_add_executor_job(_write, path, current)

        if self.post_write_hook is not None:
            hass.async_create_task(self.post_write_hook(ACTION_DELETE, config_key))

        return self.json({"result": "ok"})

    async def read_config(self, hass):
        """Read the config."""
        current = await hass.async_add_job(_read, hass.config.path(self.path))
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
        value = self._get_value(hass, data, config_key)

        if value is None:
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
    data = dump(data)
    with open(path, "w", encoding="utf-8") as outfile:
        outfile.write(data)
