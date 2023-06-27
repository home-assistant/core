"""Support for image which integrates with other components."""
from __future__ import annotations

import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.components.image import (
    DOMAIN as IMAGE_DOMAIN,
    ImageEntity,
)
from homeassistant.const import CONF_UNIQUE_ID, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import TriggerUpdateCoordinator
from .const import CONF_PICTURE
from .template_entity import (
    TemplateEntity,
    make_template_entity_common_schema,
)
from .trigger_entity import TriggerEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Template Image"

GET_IMAGE_TIMEOUT = 10

IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
).extend(make_template_entity_common_schema(DEFAULT_NAME).schema)


async def _async_create_entities(
    hass: HomeAssistant, definitions: list[dict[str, Any]], unique_id_prefix: str | None
) -> list[StateImageEntity]:
    """Create the template image."""
    entities = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(StateImageEntity(hass, definition, unique_id))
    return entities


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template image."""
    if discovery_info is None:
        _LOGGER.warning(
            "Template image entities can only be configured under template:"
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerImageEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    async_add_entities(
        await _async_create_entities(
            hass, discovery_info["entities"], discovery_info["unique_id"]
        )
    )


class TemplateImage(ImageEntity):
    """Base class for templated image."""

    _last_image: bytes | None = None
    _url: str | None = None
    _verify_ssl: bool

    def __init__(self, hass: HomeAssistant, verify_ssl: bool) -> None:
        """Initialize the image."""
        super().__init__(hass)
        self._verify_ssl = verify_ssl

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if self._last_image:
            return self._last_image

        if not (url := self._url):
            return None

        try:
            async_client = get_async_client(self.hass, verify_ssl=self._verify_ssl)
            response = await async_client.get(
                url, timeout=GET_IMAGE_TIMEOUT, follow_redirects=True
            )
            response.raise_for_status()
            self._attr_content_type = response.headers["content-type"]
            self._last_image = response.content
            return self._last_image
        except httpx.TimeoutException:
            _LOGGER.error("%s: Timeout getting image from %s", self.entity_id, url)
            return None
        except (httpx.RequestError, httpx.HTTPStatusError) as err:
            _LOGGER.error(
                "%s: Error getting new image from %s: %s",
                self.entity_id,
                url,
                err,
            )
            return None


class StateImageEntity(TemplateEntity, TemplateImage):
    """Representation of a template image."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the image."""
        TemplateEntity.__init__(self, hass, config=config, unique_id=unique_id)
        TemplateImage.__init__(self, hass, config[CONF_VERIFY_SSL])
        self._url_template = config[CONF_URL]

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        if self._entity_picture_template:
            return TemplateEntity.entity_picture.fget(self)  # type: ignore[attr-defined]
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]

    @callback
    def _update_url(self, result):
        if isinstance(result, TemplateError):
            self._url = None
            return
        self._attr_image_last_updated = dt_util.utcnow()
        self._last_image = None
        self._url = result

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.add_template_attribute("_url", self._url_template, None, self._update_url)
        await super().async_added_to_hass()


class TriggerImageEntity(TriggerEntity, TemplateImage):
    """Image entity based on trigger data."""

    _last_image: bytes | None = None

    domain = IMAGE_DOMAIN
    extra_template_keys = (CONF_URL,)

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: dict,
    ) -> None:
        """Initialize the entity."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        TemplateImage.__init__(self, hass, config[CONF_VERIFY_SSL])

    @property
    def entity_picture(self) -> str | None:
        """Return entity picture."""
        # mypy doesn't know about fget: https://github.com/python/mypy/issues/6185
        if CONF_PICTURE in self._config:
            return TriggerEntity.entity_picture.fget(self)  # type: ignore[attr-defined]
        return ImageEntity.entity_picture.fget(self)  # type: ignore[attr-defined]

    @callback
    def _process_data(self) -> None:
        """Process new data."""
        super()._process_data()
        self._attr_image_last_updated = dt_util.utcnow()
        self._last_image = None
        self._url = self._rendered.get(CONF_URL)
