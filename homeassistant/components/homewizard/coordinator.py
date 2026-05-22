"""Update coordinator for HomeWizard."""

from homewizard_energy import HomeWizardEnergy
from homewizard_energy.errors import DisabledError, RequestError, UnauthorizedError
from homewizard_energy.models import Batteries, CombinedModels as DeviceResponseEntry

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, ISSUE_BATTERY_MODE_CLOUD_DISABLED, LOGGER, UPDATE_INTERVAL

type HomeWizardConfigEntry = ConfigEntry[HWEnergyDeviceUpdateCoordinator]


def _battery_mode_cloud_issue_id(entry_id: str) -> str:
    """Build issue id for battery mode/cloud incompatibility."""
    return f"{ISSUE_BATTERY_MODE_CLOUD_DISABLED}_{entry_id}"


class HWEnergyDeviceUpdateCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Gather data for the energy device."""

    api: HomeWizardEnergy
    api_disabled: bool = False

    config_entry: HomeWizardConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HomeWizardConfigEntry,
        api: HomeWizardEnergy,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Fetch all device and sensor data from api."""
        try:
            data = await self.api.combined()

        except RequestError as ex:
            # pylint: disable-next=home-assistant-exception-message-with-translation
            raise UpdateFailed(
                ex, translation_domain=DOMAIN, translation_key="communication_error"
            ) from ex

        except DisabledError as ex:
            if not self.api_disabled:
                self.api_disabled = True

                # Do not reload when performing first refresh
                if self.data is not None:
                    # Reload config entry to let init flow handle
                    # retrying and trigger repair flow
                    self.hass.config_entries.async_schedule_reload(
                        self.config_entry.entry_id
                    )

            # pylint: disable-next=home-assistant-exception-message-with-translation
            raise UpdateFailed(
                ex, translation_domain=DOMAIN, translation_key="api_disabled"
            ) from ex

        except UnauthorizedError as ex:
            raise ConfigEntryAuthFailed from ex

        self.api_disabled = False
        issue_id = _battery_mode_cloud_issue_id(self.config_entry.entry_id)
        if (
            data.batteries is not None
            and data.system is not None
            and data.batteries.mode == str(Batteries.Mode.PREDICTIVE)
            and data.system.cloud_enabled is False
        ):
            async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                is_persistent=False,
                translation_key=ISSUE_BATTERY_MODE_CLOUD_DISABLED,
                severity=IssueSeverity.ERROR,
                data={"entry_id": self.config_entry.entry_id},
            )
        else:
            async_delete_issue(self.hass, DOMAIN, issue_id)

        self.data = data
        return data
