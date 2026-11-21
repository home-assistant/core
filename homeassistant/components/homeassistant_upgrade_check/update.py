"""Mock core update for the Home Assistant Upgrade Check integration.

Stands in for hassio's SupervisorCoreUpdateEntity where there is no Supervisor.
"""

from typing import Any, override

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .mock import MOCK_CORE_UPDATE_ID, MOCK_RELEASE_URL, MOCK_RUNNING, MOCK_TARGET


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the mock core update entity."""
    async_add_entities([MockCoreUpdateEntity()])


class MockCoreUpdateEntity(UpdateEntity):
    """A core update from MOCK_RUNNING to MOCK_TARGET that cannot install."""

    _attr_has_entity_name = True
    _attr_translation_key = "core"
    _attr_unique_id = MOCK_CORE_UPDATE_ID
    _attr_should_poll = False
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_title = "Home Assistant Core"
    _attr_installed_version = MOCK_RUNNING
    _attr_latest_version = MOCK_TARGET
    _attr_release_url = MOCK_RELEASE_URL

    @property
    @override
    def entity_picture(self) -> str | None:
        """Use the same picture as hassio's core update entity."""
        return "/api/brands/integration/homeassistant/icon.png?placeholder=no"

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Refuse to install; there is nothing to upgrade to on dev."""
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="mock_install"
        )
