"""Common helper and classes for number entity tests."""

from homeassistant.components.number import NumberEntity, RestoreNumber

from tests.common import MockEntity


class MockNumberEntity(MockEntity, NumberEntity):
    """Mock number class."""

    @property
    def native_max_value(self):
        """Return the native native_max_value."""
        return self._handle("native_max_value")

    @property
    def native_min_value(self):
        """Return the native native_min_value."""
        return self._handle("native_min_value")

    @property
    def native_step(self):
        """Return the native native_step."""
        return self._handle("native_step")

    @property
    def native_unit_of_measurement(self):
        """Return the native unit_of_measurement."""
        return self._handle("native_unit_of_measurement")

    @property
    def native_value(self):
        """Return the native value of this number."""
        return self._handle("native_value")

    def set_native_value(self, value: float) -> None:
        """Change the selected option."""
        self._values["native_value"] = value


class MockRestoreNumber(MockNumberEntity, RestoreNumber):
    """Mock RestoreNumber class."""

    async def async_added_to_hass(self) -> None:
        """Restore native_*."""
        await super().async_added_to_hass()
        if (last_number_data := await self.async_get_last_number_data()) is None:
            return
        self._values["native_max_value"] = last_number_data.native_max_value
        self._values["native_min_value"] = last_number_data.native_min_value
        self._values["native_step"] = last_number_data.native_step
        self._values["native_unit_of_measurement"] = (
            last_number_data.native_unit_of_measurement
        )
        self._values["native_value"] = last_number_data.native_value
