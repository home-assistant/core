"""Edifier infrared integration for Home Assistant."""

from infrared_protocols.codes.edifier.models import (
    MODEL_TO_COMMAND_SET,
    EdifierCommandSet,
    EdifierModel,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODEL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_COMMAND_SET, CONF_INFRARED_ENTITY_ID, DOMAIN

PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Edifier IR from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate old config entries."""
    if entry.version == 1:
        data = {**entry.data}
        # The R1700BT model was renamed to R1700BT (pre-2017), and its
        # command set was split from the one shared with the R1700BTs
        # family, which it was incorrectly grouped with.
        if data[CONF_MODEL] == "R1700BT":
            data[CONF_MODEL] = EdifierModel.R1700BT_PRE_2017.value
        command_set = MODEL_TO_COMMAND_SET[EdifierModel(data[CONF_MODEL])]
        data[CONF_COMMAND_SET] = command_set.value
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            unique_id=f"{command_set.value}_{data[CONF_INFRARED_ENTITY_ID]}",
            version=2,
        )

    if entry.version == 2:
        data = {**entry.data}
        # The R2000DB and R2730DB/RC10D1 models got their own command sets,
        # split from the R1280DB one, which they were incorrectly grouped with.
        command_set = MODEL_TO_COMMAND_SET[EdifierModel(data[CONF_MODEL])]
        data[CONF_COMMAND_SET] = command_set.value
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            unique_id=f"{command_set.value}_{data[CONF_INFRARED_ENTITY_ID]}",
            version=3,
        )

    if entry.version == 3:
        data = {**entry.data}
        # The RC80B and RC31A models got their own command sets, split from
        # the R1700BTs and S360DB ones, which they were incorrectly grouped with.
        command_set = MODEL_TO_COMMAND_SET[EdifierModel(data[CONF_MODEL])]
        if command_set is EdifierCommandSet.RC80B:
            # The R1700BTs Line 1 and Line 2 codes are the RC80B Opt/Coax and
            # Line 1/2 toggles, so keep the existing button entities.
            renamed_keys = {"line_1": "opt_coax", "line_2": "line_1_2"}

            @callback
            def _migrate_unique_id(
                entity_entry: er.RegistryEntry,
            ) -> dict[str, str] | None:
                key = entity_entry.unique_id.removeprefix(f"{entry.entry_id}_")
                if key not in renamed_keys:
                    return None
                return {"new_unique_id": f"{entry.entry_id}_{renamed_keys[key]}"}

            await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)
        elif command_set is EdifierCommandSet.R2600:
            # The R2600 command set has no Bluetooth, optical or coaxial input.
            entity_registry = er.async_get(hass)
            for key in ("bluetooth", "optical", "coax"):
                if entity_id := entity_registry.async_get_entity_id(
                    Platform.BUTTON, DOMAIN, f"{entry.entry_id}_{key}"
                ):
                    entity_registry.async_remove(entity_id)
        data[CONF_COMMAND_SET] = command_set.value
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            unique_id=f"{command_set.value}_{data[CONF_INFRARED_ENTITY_ID]}",
            version=4,
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload an Edifier IR config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
