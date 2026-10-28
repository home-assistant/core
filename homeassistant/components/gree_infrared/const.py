"""Constants for the Gree IR integration."""

from infrared_protocols.commands.gree_ac import GreeAcMode

from homeassistant.components.climate import HVACMode

DOMAIN = "gree_infrared"
CONF_INFRARED_EMITTER_ENTITY_ID = "infrared_emitter_entity_id"
CONF_INFRARED_RECEIVER_ENTITY_ID = "infrared_receiver_entity_id"
CONF_HVAC_MODES = "hvac_modes"

DEFAULT_HVAC_MODES = [HVACMode.COOL, HVACMode.DRY]

# Every mode other than OFF; the protocol has no OFF mode of its own, power is a
# separate field, so this dict intentionally has no HVACMode.OFF entry.
HA_MODE_TO_LIB: dict[HVACMode, GreeAcMode] = {
    HVACMode.AUTO: GreeAcMode.AUTO,
    HVACMode.COOL: GreeAcMode.COOL,
    HVACMode.HEAT: GreeAcMode.HEAT,
    HVACMode.DRY: GreeAcMode.DRY,
    HVACMode.FAN_ONLY: GreeAcMode.FAN_ONLY,
}
LIB_MODE_TO_HA: dict[GreeAcMode, HVACMode] = {v: k for k, v in HA_MODE_TO_LIB.items()}
