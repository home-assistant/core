"""Switch platform for Hass.io."""

from typing import Any, override

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import AddonState

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .auto_update import AutoUpdateUnavailableReason
from .const import ADDONS_COORDINATOR, DATA_AUTO_UPDATE, MAIN_COORDINATOR
from .entity import HassioAddonEntity, HassioCoreEntity
from .handler import get_supervisor_client

ENTITY_DESCRIPTION = SwitchEntityDescription(
    key="state",
    name=None,
    icon="mdi:puzzle",
    entity_registry_enabled_default=False,
)

CORE_AUTO_UPDATE_DESCRIPTION = SwitchEntityDescription(
    key="auto_update",
    translation_key="core_auto_update",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Switch set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    async_add_entities(
        HassioAddonSwitch(
            addon=addon,
            coordinator=coordinator,
            entity_description=ENTITY_DESCRIPTION,
        )
        for addon in coordinator.data.addons.values()
    )

    # Being Home Assistant OS does not change while running, but the channel
    # can; off the stable channel the switch is unavailable instead of missing
    if (
        hass.data[DATA_AUTO_UPDATE].unavailable_reason
        is not AutoUpdateUnavailableReason.NOT_HOME_ASSISTANT_OS
    ):
        async_add_entities(
            [
                HassioCoreAutoUpdateSwitch(
                    coordinator=hass.data[MAIN_COORDINATOR],
                    entity_description=CORE_AUTO_UPDATE_DESCRIPTION,
                )
            ]
        )


class HassioAddonSwitch(HassioAddonEntity, SwitchEntity):
    """Switch for Hass.io add-ons."""

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the add-on is on."""
        return (
            self.coordinator.data.addons[self._addon_slug].addon.state
            == AddonState.STARTED
        )

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the icon of the add-on if any."""
        if not self.available:
            return None
        if self.coordinator.data.addons[self._addon_slug].addon.icon:
            return f"/api/hassio/addons/{self._addon_slug}/icon"
        return None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        supervisor_client = get_supervisor_client(self.hass)
        try:
            await supervisor_client.addons.start_addon(self._addon_slug)
        except SupervisorError as err:
            raise HomeAssistantError(err) from err

        await self.coordinator.force_addon_info_data_refresh(self._addon_slug)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        supervisor_client = get_supervisor_client(self.hass)
        try:
            await supervisor_client.addons.stop_addon(self._addon_slug)
        except SupervisorError as err:
            raise HomeAssistantError(err) from err

        await self.coordinator.force_addon_info_data_refresh(self._addon_slug)


class HassioCoreAutoUpdateSwitch(HassioCoreEntity, SwitchEntity):
    """Switch to pause automatic Home Assistant updates, like from automations."""

    @property
    @override
    def available(self) -> bool:
        """Return if automatic updates are possible on this installation."""
        return (
            super().available
            and self.hass.data[DATA_AUTO_UPDATE].unavailable_reason is None
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return if automatic updates are on; not chosen yet counts as off."""
        return self.hass.data[DATA_AUTO_UPDATE].settings.enabled is True

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the setting when it changes elsewhere, like on the settings page."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.config_entry.add_update_listener(self._async_entry_updated)
        )

    async def _async_entry_updated(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Write the state after the settings changed."""
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn automatic updates on."""
        self.hass.data[DATA_AUTO_UPDATE].async_set_enabled(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn automatic updates off."""
        self.hass.data[DATA_AUTO_UPDATE].async_set_enabled(False)
