"""The foscam component."""

import base64
from http import HTTPStatus

from aiohttp.web import Request, Response
from libpyfoscamcgi import FoscamCamera
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.components.webhook import async_generate_url
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries

from .config_flow import DEFAULT_RTSP_PORT
from .const import (
    CONF_RTSP_PORT,
    CONF_WEBHOOK_ID,
    DOMAIN,
    LOGGER,
    VALUE1,
    VALUE2,
    VALUE3,
)
from .coordinator import FoscamConfigEntry, FoscamCoordinator

PLATFORMS = [Platform.CAMERA, Platform.EVENT, Platform.NUMBER, Platform.SWITCH]

WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(VALUE1): str,
        vol.Required(VALUE2): str,
        vol.Required(VALUE3): str,
    }
)


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Response:
    """Handle foscam webhook request."""
    try:
        data = WEBHOOK_SCHEMA(await request.json())
    except vol.MultipleInvalid as error:
        return Response(
            text=error.error_message, status=HTTPStatus.UNPROCESSABLE_ENTITY
        )

    async_dispatcher_send(hass, DOMAIN, webhook_id, data)
    return Response(status=HTTPStatus.OK)


async def async_setup_entry(hass: HomeAssistant, entry: FoscamConfigEntry) -> bool:
    """Set up foscam from a config entry."""

    session = FoscamCamera(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        verbose=False,
    )

    coordinator = FoscamCoordinator(hass, entry, session)
    webhook.async_register(
        hass, DOMAIN, entry.title, entry.data[CONF_WEBHOOK_ID], handle_webhook
    )
    webhook_url = async_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
    encoded_url = base64.urlsafe_b64encode(webhook_url.encode("utf-8")).decode("utf-8")
    await hass.async_add_executor_job(
        coordinator.session.setAlarmHttpServer, encoded_url
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Migrate to correct unique IDs for switches
    await async_migrate_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FoscamConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: FoscamConfigEntry) -> bool:
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        # Change unique id
        @callback
        def update_unique_id(entry):
            return {"new_unique_id": entry.entry_id}

        await async_migrate_entries(hass, entry.entry_id, update_unique_id)

        # Get RTSP port from the camera or use the fallback one and store it in data
        camera = FoscamCamera(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            verbose=False,
        )

        ret, response = await hass.async_add_executor_job(camera.get_port_info)

        rtsp_port = DEFAULT_RTSP_PORT

        if ret != 0:
            rtsp_port = response.get("rtspPort") or response.get("mediaPort")

        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_RTSP_PORT: rtsp_port},
            version=2,
            unique_id=None,
        )

    LOGGER.debug("Migration to version %s successful", entry.version)

    return True


async def async_migrate_entities(hass: HomeAssistant, entry: FoscamConfigEntry) -> None:
    """Migrate old entries to support config_entry_id-based unique IDs."""

    @callback
    def _update_unique_id(
        entity_entry: RegistryEntry,
    ) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if (
            entity_entry.domain == Platform.SWITCH
            and entity_entry.unique_id == "sleep_switch"
        ):
            entity_new_unique_id = f"{entity_entry.config_entry_id}_sleep_switch"
            return {"new_unique_id": entity_new_unique_id}

        return None

    # Migrate entities
    await async_migrate_entries(hass, entry.entry_id, _update_unique_id)
