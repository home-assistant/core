"""The Homewizard integration."""

from homewizard_energy import HomeWizardEnergy, HomeWizardEnergyV1, HomeWizardEnergyV2

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import HWEnergyDeviceUpdateCoordinator

type HomeWizardConfigEntry = ConfigEntry[HWEnergyDeviceUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HomeWizardConfigEntry) -> bool:
    """Set up Homewizard from a config entry."""

    api: HomeWizardEnergy

    if token := entry.data.get(CONF_TOKEN):
        api = HomeWizardEnergyV2(
            entry.data[CONF_IP_ADDRESS],
            token=token,
            clientsession=async_get_clientsession(hass),
        )
    else:
        api = HomeWizardEnergyV1(
            entry.data[CONF_IP_ADDRESS],
            clientsession=async_get_clientsession(hass),
        )

    coordinator = HWEnergyDeviceUpdateCoordinator(hass, api)
    try:
        await coordinator.async_config_entry_first_refresh()

    except ConfigEntryNotReady:
        await coordinator.api.close()

        if coordinator.api_disabled:
            entry.async_start_reauth(hass)

        raise

    entry.runtime_data = coordinator

    # Abort reauth config flow if active
    for progress_flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        if (
            "context" in progress_flow
            and progress_flow["context"].get("source") == SOURCE_REAUTH
        ):
            hass.config_entries.flow.async_abort(progress_flow["flow_id"])

    # Finalize
    entry.async_on_unload(coordinator.api.close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HomeWizardConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
