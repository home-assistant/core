"""Kodi notification service."""

import logging
from typing import Any, override

import aiohttp
import jsonrpc_async
from jsonrpc_base.jsonrpc import ProtocolError, TransportError
import probatio
from pykodi import CannotConnectError, Kodi

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    DOMAIN as NOTIFY_DOMAIN,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.const import (
    ATTR_ICON,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROXY_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import KodiConfigEntry
from .const import (
    CONF_NOTIFY_LINKED,
    DEFAULT_NOTIFY_DISPLAYTIME,
    DEFAULT_NOTIFY_ICON,
    DOMAIN,
)
from .issue import DATA_YAML_NOTIFY, YamlNotifyConfig, async_create_notify_entity_issue

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8080
DEFAULT_PROXY_SSL = False
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(CONF_PROXY_SSL, default=DEFAULT_PROXY_SSL): cv.boolean,
        probatio.Inclusive(CONF_USERNAME, "auth"): cv.string,
        probatio.Inclusive(probatio.Secret(CONF_PASSWORD), "auth"): cv.string,
    }
)

ATTR_DISPLAYTIME = "displaytime"


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> KodiNotificationService:
    """Return the notify service."""
    username: str | None = config.get(CONF_USERNAME)
    password: str | None = config.get(CONF_PASSWORD)

    host: str = config[CONF_HOST]
    port: int = config[CONF_PORT]
    encryption = config.get(CONF_PROXY_SSL)

    if host.startswith(("http://", "https://")):
        host = host[host.index("://") + 3 :]
        _LOGGER.warning(
            "Kodi host name should no longer contain http:// See updated "
            "definitions here: "
            "https://www.home-assistant.io/integrations/kodi/"
        )

    http_protocol = "https" if encryption else "http"
    url = f"{http_protocol}://{host}:{port}/jsonrpc"

    if username is not None and password is not None:
        auth = aiohttp.BasicAuth(username, password)
    else:
        auth = None

    return KodiNotificationService(hass, url, auth)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KodiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Kodi notify entity."""
    if (uid := entry.unique_id) is None:
        uid = entry.entry_id
    if yaml_configs := [
        yaml_config
        for yaml_config in hass.data.get(DATA_YAML_NOTIFY, [])
        if yaml_config.matches(entry.data)
    ]:
        _async_link_yaml_notify(hass, entry, uid, yaml_configs)

    async_add_entities(
        [KodiNotifyEntity(entry.runtime_data.kodi, entry.data[CONF_NAME], uid)]
    )


@callback
def _async_link_yaml_notify(
    hass: HomeAssistant,
    entry: KodiConfigEntry,
    uid: str,
    yaml_configs: list[YamlNotifyConfig],
) -> None:
    """Name the notify entity after the YAML notify platform and raise the issues."""
    # The first YAML name names a new entity; once linked, the entity keeps its ID
    name = None if entry.data.get(CONF_NOTIFY_LINKED) else yaml_configs[0].name
    registry_entry = er.async_get(hass).async_get_or_create(
        NOTIFY_DOMAIN,
        DOMAIN,
        uid,
        config_entry=entry,
        suggested_object_id=slugify(name or entry.data[CONF_NAME]),
    )
    if not entry.data.get(CONF_NOTIFY_LINKED):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_NOTIFY_LINKED: True}
        )
    for yaml_config in yaml_configs:
        async_create_notify_entity_issue(
            hass, yaml_config, registry_entry.entity_id, entry.title
        )


class KodiNotificationService(BaseNotificationService):
    """Implement the notification service for Kodi."""

    def __init__(self, hass, url, auth=None):
        """Initialize the service."""
        self._url = url

        kwargs = {"timeout": DEFAULT_TIMEOUT, "session": async_get_clientsession(hass)}

        if auth is not None:
            kwargs["auth"] = auth

        self._server = jsonrpc_async.Server(self._url, **kwargs)

    @override
    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to Kodi."""
        try:
            data = kwargs.get(ATTR_DATA) or {}

            displaytime = int(data.get(ATTR_DISPLAYTIME, 10000))
            icon = data.get(ATTR_ICON, "info")
            title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
            await self._server.GUI.ShowNotification(title, message, icon, displaytime)

        except jsonrpc_async.TransportError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notify_failed",
            ) from err


class KodiNotifyEntity(NotifyEntity):
    """Notify entity of a Kodi device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, kodi: Kodi, name: str, uid: str) -> None:
        """Initialize the notify entity."""
        self._kodi = kodi
        self._attr_unique_id = uid
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="Kodi",
            name=name,
        )

    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send the message via the notify.send_message action."""
        await self._async_send(message, title)

    async def kodi_send_message(
        self,
        message: str,
        icon: str,
        displaytime: int,
        title: str | None = None,
    ) -> None:
        """Send the message via the kodi.send_message action."""
        await self._async_send(message, title, icon, displaytime)
        self._async_record_notification()

    async def _async_send(
        self,
        message: str,
        title: str | None,
        icon: str = DEFAULT_NOTIFY_ICON,
        displaytime: int = DEFAULT_NOTIFY_DISPLAYTIME,
    ) -> None:
        """Show the notification on the Kodi device."""
        try:
            await self._kodi.send_notification(
                title or ATTR_TITLE_DEFAULT, message, icon, displaytime
            )
        except (TransportError, ProtocolError, CannotConnectError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notify_failed",
            ) from err
