"""Common helpers for select entity component tests."""

from homeassistant.components.select import SelectEntity

from tests.common import MockEntity


class MockSelectEntity(MockEntity, SelectEntity):
    """Mock Select class."""

    @property
    def current_option(self):
        """Return the current option of this select."""
        return self._handle("current_option")

    @property
    def options(self) -> list:
        """Return the list of available options of this select."""
        return self._handle("options")

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._values["current_option"] = option
