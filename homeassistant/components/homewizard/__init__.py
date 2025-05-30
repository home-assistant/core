"""The Homewizard integration."""

from homewizard_energy import (
    HomeWizardEnergy,
    HomeWizardEnergyV1,
    HomeWizardEnergyV2,
    has_v2_api,
)

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, PLATFORMS
from .coordinator import HomeWizardConfigEntry, HWEnergyDeviceUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: HomeWizardConfigEntry) -> bool:
    """Set up Homewizard from a config entry."""

    api: HomeWizardEnergy

    is_battery = entry.unique_id.startswith("HWE-BAT") if entry.unique_id else False

    if (token := entry.data.get(CONF_TOKEN)) and is_battery:
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

        if is_battery:
            await async_check_v2_support_and_create_issue(hass, entry)

    coordinator = HWEnergyDeviceUpdateCoordinator(hass, entry, api)
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


async def async_check_v2_support_and_create_issue(
    hass: HomeAssistant, entry: HomeWizardConfigEntry
) -> None:
    """Check if the device supports v2 and create an issue if not."""

    if not await has_v2_api(entry.data[CONF_IP_ADDRESS], async_get_clientsession(hass)):
        return

    async_create_issue(
        hass,
        DOMAIN,
        f"migrate_to_v2_api_{entry.entry_id}",
        is_fixable=True,
        is_persistent=False,
        learn_more_url="https://home-assistant.io/integrations/homewizard/#which-button-do-i-need-to-press-to-configure-the-device",
        translation_key="migrate_to_v2_api",
        translation_placeholders={
            "title": entry.title,
        },
        severity=IssueSeverity.WARNING,
        data={"entry_id": entry.entry_id},
    )
