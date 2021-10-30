"""Support for ADS switch platform."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME, CONF_SWITCHES

from . import CONF_ADS_VAR, DATA_ADS, STATE_KEY_STATE, AdsEntity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up switch platform for ADS."""
    entities = []

    if discovery_info is None:  # pragma: no cover
        return

    ads_hub = hass.data.get(DATA_ADS)

    for entry in discovery_info[CONF_SWITCHES]:
        ads_var = entry.get(CONF_ADS_VAR)
        name = entry.get(CONF_NAME)
        entities.append(AdsSwitch(ads_hub, name, ads_var))

    add_entities(entities)


class AdsSwitch(AdsEntity, SwitchEntity):
    """Representation of an ADS switch device."""

    async def async_added_to_hass(self):
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, self._ads_hub.PLCTYPE_BOOL)

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._ads_hub.write_by_name(self._ads_var, True, self._ads_hub.PLCTYPE_BOOL)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._ads_hub.write_by_name(self._ads_var, False, self._ads_hub.PLCTYPE_BOOL)
