"""Demo platform that offers a fake Number entity."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the demo Number entity."""
    async_add_entities(
        [
            DemoNumber(
                "volume1",
                "volume",
                42.0,
                "mdi:volume-high",
                False,
                mode=NumberMode.SLIDER,
            ),
            DemoNumber(
                "pwm1",
                "PWM 1",
                0.42,
                "mdi:square-wave",
                False,
                0.0,
                1.0,
                0.01,
                NumberMode.BOX,
            ),
            DemoNumber(
                "large_range",
                "Large Range",
                500,
                "mdi:square-wave",
                False,
                1,
                1000,
                1,
            ),
            DemoNumber(
                "small_range",
                "Small Range",
                128,
                "mdi:square-wave",
                False,
                1,
                255,
                1,
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoNumber(NumberEntity):
    """Representation of a demo Number entity."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        state: float,
        icon: str,
        assumed: bool,
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        mode: NumberMode = NumberMode.AUTO,
    ) -> None:
        """Initialize the Demo Number entity."""
        self._attr_assumed_state = assumed
        self._attr_icon = icon
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_unique_id = unique_id
        self._attr_value = state
        self._attr_mode = mode

        if min_value is not None:
            self._attr_min_value = min_value
        if max_value is not None:
            self._attr_max_value = max_value
        if step is not None:
            self._attr_step = step

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            name=self.name,
        )

    async def async_set_value(self, value):
        """Update the current value."""
        self._attr_value = value
        self.async_write_ha_state()
