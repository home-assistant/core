"""Base class for all Songpal entities."""

import logging
import re

from songpal.containers import Setting

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SongpalCoordinator
from .device import device_info, device_unique_id

_LOGGER = logging.getLogger(__name__)


class SongpalBaseEntity(CoordinatorEntity[SongpalCoordinator]):
    """Songpal Base Entity Class.

    This provides shared functionality between all Songpal entities.
    """

    _attr_has_entity_name = True

    @callback
    def update_state(self, data) -> None:
        """Process data from coordinator."""

        raise NotImplementedError("Songpal entity failed to override update_state")

    def get_initial_state(self) -> None:
        """Fetch & process data from coordinator when entity is created."""
        self.update_state(self.coordinator.data)
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update latest data from coordinator."""
        # This method is called by SongpalCoordinator when a successful update runs.
        self.update_state(self.coordinator.data)
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return device_info(self.coordinator.device_name, self.coordinator.data)


class SongpalSettingEntity(SongpalBaseEntity):
    """Base class for songpal entities that expose a single setting."""

    setting: Setting | None

    def __init__(
        self,
        coordinator: SongpalCoordinator,
        setting_bank: str,
        setting: Setting,
    ) -> None:
        """Init."""

        self._setting_bank = setting_bank
        self._setting_target = setting.target
        self._settingName = self.get_friendly_setting_name(setting.target)
        self._settingId = (
            f"{self._setting_bank}_{self._settingName.replace(' ', '_').lower()}"
        )

        self.setting = setting

        super().__init__(coordinator)

    def update_state(self, data) -> None:
        """Process data from coordinator."""

        for setting in self.coordinator.data[self._setting_bank]:
            if setting.target == self._setting_target:
                self.setting = setting
                break
        else:
            self.setting = None

    def get_friendly_setting_name(self, setting_name):
        """Convert setting name from camelCase to space-delimited words."""

        return " ".join(
            word if len(word) > 1 and word.isupper() else word.lower()
            for word in re.sub(
                "([A-Z][a-z]+)", r" \1", re.sub("([A-Z]+)", r" \1", setting_name)
            ).split()
        )

    @property
    def name(self) -> str:
        """Return the friendly name of the entity."""
        return self._settingName

    @property
    def unique_id(self) -> str:
        """Return unique id."""

        return f"{DOMAIN}-{device_unique_id(self.coordinator.data)}-{self._settingId}"
