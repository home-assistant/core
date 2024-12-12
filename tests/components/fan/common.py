"""Collection of helpers."""

from homeassistant.components.fan import FanEntity

from tests.common import MockEntity


class MockFan(MockEntity, FanEntity):
    """Mock Fan class."""

    @property
    def preset_modes(self) -> list[str] | None:
        """Return preset mode."""
        return self._handle("preset_modes")

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode
