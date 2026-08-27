"""Select platform for the BLUETTI integration."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BluettiConfigEntry
from .const import DOMAIN
from .entity import BluettiEntity
from .models import BluettiData, BluettiDevice, BluettiState

# Select actions call the BLUETTI cloud API; serialize them to avoid
# hammering it with concurrent control requests.
PARALLEL_UPDATES = 1

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Bluetti selects from config entry."""
    bluetti_devices: BluettiData = config_entry.runtime_data.bluetti_devices

    entities: list[BluettiSelect] = []
    for device in bluetti_devices.devices:
        entities.extend(
            BluettiSelect(device, state)
            for state in device.states
            if state.fn_type == "SELECT" and state.support_mode_values
        )

    if entities:
        async_add_entities(entities)

    return True


class BluettiSelect(BluettiEntity, SelectEntity):
    """Representation of a Bluetti select (mode choice)."""

    def __init__(self, device: BluettiDevice, state: BluettiState) -> None:
        """Initialize the select from its owning device and cloud state."""
        super().__init__(device, state)
        self._attr_name = state.fn_name

        self._attr_options = [v["name"] for v in state.support_mode_values]

        # Some fn_codes (e.g. InvWorkState) only report a mode, they cannot
        # be changed by the user.
        self._readonly = state.fn_code == "InvWorkState"

        # Keep _attr_options populated even when read-only, so current_option
        # (sourced from the device's reported value) is never outside of the
        # advertised options list - Home Assistant would otherwise log a
        # "not in the list of available options" warning on every update.
        if self._readonly:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def current_option(self) -> str:
        """Return the device's current mode, as a display name."""
        return self._state_obj.get_name_for_value()

    async def async_select_option(self, option: str) -> None:
        """Change to the given mode, by its display name."""
        if self._readonly:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="select_option_read_only",
                translation_placeholders={"fn_code": self._state_obj.fn_code},
            )

        for v in self._state_obj.support_mode_values:
            if v["name"] == option:
                await self._device.set_state_value(self._state_obj.fn_code, v["code"])
                return
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="select_option_invalid",
            translation_placeholders={"option": option, "fn_code": self._state_obj.fn_code},
        )
