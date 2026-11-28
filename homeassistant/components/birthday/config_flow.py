"""Config flow for the Birthday integration."""

import calendar
from types import MappingProxyType
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAY,
    CONF_MONTH,
    CONF_PERSON,
    CONF_YEAR,
    DOMAIN,
    SUBENTRY_TYPE_BIRTHDAY,
)

CONF_ADD_ANOTHER = "add_another"
MIN_YEAR = 1900
LEAP_YEAR = 2000


def _number() -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(step=1, mode=NumberSelectorMode.BOX))


def _schema(*, allow_add_another: bool) -> probatio.Schema:
    schema: dict[Any, Any] = {
        probatio.Required(CONF_PERSON): str,
        probatio.Required(CONF_DAY): _number(),
        probatio.Required(CONF_MONTH): _number(),
        probatio.Optional(CONF_YEAR): _number(),
    }
    if allow_add_another:
        schema[probatio.Optional(CONF_ADD_ANOTHER, default=False)] = bool
    return probatio.Schema(schema)


def _title(birthday: dict[str, Any]) -> str:
    """Build the title shown in the integration page."""
    text = (
        f"{birthday[CONF_PERSON]} – {birthday[CONF_DAY]:02d}/{birthday[CONF_MONTH]:02d}"
    )
    if year := birthday.get(CONF_YEAR):
        text += f"/{year}"
    return text


def _parse(
    user_input: dict[str, Any], existing: list[str]
) -> tuple[dict[str, Any], dict[str, str], dict[str, str]]:
    """Validate the input. Return (birthday, errors, description placeholders)."""
    max_year = dt_util.now().year
    placeholders = {
        "min_year": str(MIN_YEAR),
        "max_year": str(max_year),
        "max_day": "31",
        "year": "",
    }
    errors: dict[str, str] = {}

    name = user_input[CONF_PERSON].strip()
    if not name:
        errors[CONF_PERSON] = "name_empty"
    elif name.casefold() in {n.casefold() for n in existing}:
        errors[CONF_PERSON] = "name_exists"

    for field in (CONF_DAY, CONF_MONTH, CONF_YEAR):
        if field == CONF_YEAR and user_input.get(field) is None:
            continue
        if not float(user_input[field]).is_integer():
            errors[field] = f"invalid_{field}"
    if any(field in errors for field in (CONF_DAY, CONF_MONTH, CONF_YEAR)):
        return {}, errors, placeholders

    year: int | None = None
    if (raw_year := user_input.get(CONF_YEAR)) is not None:
        year = int(raw_year)
        placeholders["year"] = str(year)
        if not MIN_YEAR <= year <= max_year:
            errors[CONF_YEAR] = "invalid_year"

    month = int(user_input[CONF_MONTH])
    day = int(user_input[CONF_DAY])

    month_valid = 1 <= month <= 12
    if not month_valid:
        errors[CONF_MONTH] = "invalid_month"

    check_year = year if year is not None and CONF_YEAR not in errors else LEAP_YEAR
    max_day = calendar.monthrange(check_year, month)[1] if month_valid else 31
    placeholders["max_day"] = str(max_day)
    if not 1 <= day <= max_day:
        errors[CONF_DAY] = (
            "not_leap_year" if month == 2 and day == 29 else "invalid_day"
        )

    birthday: dict[str, Any] = {CONF_PERSON: name, CONF_DAY: day, CONF_MONTH: month}
    if year is not None:
        birthday[CONF_YEAR] = year
    return birthday, errors, placeholders


class BirthdayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._birthdays: list[dict[str, Any]] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect one or more birthdays and create the calendar."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            birthday, errors, placeholders = _parse(
                user_input, [b[CONF_PERSON] for b in self._birthdays]
            )
            if not errors:
                self._birthdays.append(birthday)
                if not user_input.get(CONF_ADD_ANOTHER):
                    return self.async_create_entry(
                        title="Birthdays",
                        data={},
                        subentries=[
                            ConfigSubentryData(
                                data=b,
                                subentry_type=SUBENTRY_TYPE_BIRTHDAY,
                                title=_title(b),
                                unique_id=None,
                            )
                            for b in self._birthdays
                        ],
                    )
                user_input = None  # reopens the form

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _schema(allow_add_another=True), user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the subentry types supported by this integration."""
        return {SUBENTRY_TYPE_BIRTHDAY: BirthdaySubentryFlow}


class BirthdaySubentryFlow(ConfigSubentryFlow):
    """Add or edit birthdays."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add one or more birthdays."""
        return await self._async_handle(user_input, reconfigure=False)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a birthday."""
        return await self._async_handle(user_input, reconfigure=True)

    async def _async_handle(
        self, user_input: dict[str, Any] | None, *, reconfigure: bool
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry() if reconfigure else None

        if user_input is not None:
            existing = [
                s.data[CONF_PERSON]
                for s in entry.subentries.values()
                if subentry is None or s.subentry_id != subentry.subentry_id
            ]
            birthday, errors, placeholders = _parse(user_input, existing)
            if not errors:
                if subentry is not None:
                    return self.async_update_and_abort(
                        entry, subentry, title=_title(birthday), data=birthday
                    )
                if user_input.get(CONF_ADD_ANOTHER):
                    self.hass.config_entries.async_add_subentry(
                        entry,
                        ConfigSubentry(
                            data=MappingProxyType(birthday),
                            subentry_type=SUBENTRY_TYPE_BIRTHDAY,
                            title=_title(birthday),
                            unique_id=None,
                        ),
                    )
                    user_input = None
                else:
                    return self.async_create_entry(
                        title=_title(birthday), data=birthday
                    )

        suggested = user_input or (dict(subentry.data) if subentry else None)
        return self.async_show_form(
            step_id="reconfigure" if reconfigure else "user",
            data_schema=self.add_suggested_values_to_schema(
                _schema(allow_add_another=not reconfigure), suggested
            ),
            errors=errors,
            description_placeholders=placeholders,
        )
