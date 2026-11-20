"""The Compensation integration."""

import logging
from operator import itemgetter

import numpy as np
import probatio

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA as SENSOR_DEVICE_CLASSES_SCHEMA,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASSES_SCHEMA as SENSOR_STATE_CLASSES_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_SOURCE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_COMPENSATED_VALUE,
    CONF_COMPENSATION,
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_POLYNOMIAL,
    CONF_POLYNOMIAL_CONFIG,
    CONF_PRECISION,
    CONF_UNCOMPENSATED_VALUE,
    CONF_UPPER_LIMIT,
    DATA_COMPENSATION,
    DEFAULT_DEGREE,
    DEFAULT_PRECISION,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


def datapoints_greater_than_degree(value: dict) -> dict:
    """Validate data point list is greater than polynomial degrees."""
    if len(value[CONF_DATAPOINTS]) <= value[CONF_DEGREE]:
        raise probatio.Invalid(
            f"{CONF_DATAPOINTS} must have at least"
            f" {value[CONF_DEGREE] + 1} {CONF_DATAPOINTS}"
        )

    return value


COMPENSATION_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_ATTRIBUTE): cv.string,
        probatio.Required(CONF_DATAPOINTS): [
            probatio.ExactSequence([probatio.Coerce(float), probatio.Coerce(float)])
        ],
        probatio.Optional(CONF_DEGREE, default=DEFAULT_DEGREE): probatio.All(
            probatio.Coerce(int),
            probatio.Range(min=1, max=7),
        ),
        probatio.Optional(CONF_DEVICE_CLASS): SENSOR_DEVICE_CLASSES_SCHEMA,
        probatio.Optional(CONF_LOWER_LIMIT, default=False): cv.boolean,
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): cv.positive_int,
        probatio.Required(CONF_SOURCE): cv.entity_id,
        probatio.Optional(CONF_STATE_CLASS): SENSOR_STATE_CLASSES_SCHEMA,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
        probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        probatio.Optional(CONF_UPPER_LIMIT, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {cv.slug: probatio.All(COMPENSATION_SCHEMA, datapoints_greater_than_degree)}
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def create_compensation_data(
    hass: HomeAssistant, compensation: str, conf: ConfigType
) -> None:
    """Create compensation data.

    Raises FloatingPointError if no polynomial can be fitted to the data points.
    """
    _LOGGER.debug("Setup %s.%s", DOMAIN, compensation)

    degree = conf[CONF_DEGREE]

    initial_coefficients: list[tuple[float, float]] = conf[CONF_DATAPOINTS]
    sorted_coefficients = sorted(initial_coefficients, key=itemgetter(0))

    # get x values and y values from the x,y point pairs
    x_values, y_values = zip(*initial_coefficients, strict=False)

    with np.errstate(all="raise"):
        coefficients = np.polyfit(x_values, y_values, degree)

    data = {k: v for k, v in conf.items() if k not in [CONF_DEGREE, CONF_DATAPOINTS]}
    data[CONF_POLYNOMIAL] = np.poly1d(coefficients)

    if data[CONF_LOWER_LIMIT]:
        data[CONF_MINIMUM] = sorted_coefficients[0]
    else:
        data[CONF_MINIMUM] = None

    if data[CONF_UPPER_LIMIT]:
        data[CONF_MAXIMUM] = sorted_coefficients[-1]
    else:
        data[CONF_MAXIMUM] = None

    hass.data[DATA_COMPENSATION][compensation] = data


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Compensation sensor."""
    hass.data[DATA_COMPENSATION] = {}

    # Exit early if no compensations are configured using the compensation: key in configuration.yaml.
    # This allows us to create an issue if platform: compensation is present in the sensor: section.
    if DOMAIN not in config:
        return True

    for compensation, conf in config[DOMAIN].items():
        try:
            await create_compensation_data(hass, compensation, conf)
        except FloatingPointError as error:
            _LOGGER.error(
                "Setup of %s encountered an error, %s",
                compensation,
                error,
            )
            continue

        hass.async_create_task(
            async_load_platform(
                hass,
                SENSOR_DOMAIN,
                DOMAIN,
                {CONF_COMPENSATION: compensation},
                config,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Compensation from a config entry."""

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_ENTITY_ID: source_entity_id},
        )
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_ENTITY_ID]
            ),
            source_entity_id_or_uuid=entry.options[CONF_ENTITY_ID],
        )
    )

    config = dict(entry.options)
    data_points: list[dict[str, float]] = config[CONF_POLYNOMIAL_CONFIG][
        CONF_DATAPOINTS
    ]
    new_data_points = [
        [data_point[CONF_UNCOMPENSATED_VALUE], data_point[CONF_COMPENSATED_VALUE]]
        for data_point in data_points
    ]
    config[CONF_DEGREE] = config[CONF_POLYNOMIAL_CONFIG][CONF_DEGREE]
    config[CONF_DATAPOINTS] = new_data_points

    try:
        await create_compensation_data(hass, entry.entry_id, config)
    except FloatingPointError as error:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_error",
            translation_placeholders={"title": entry.title, "error": str(error)},
        ) from error
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload Compensation config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    hass.data[DATA_COMPENSATION].pop(entry.entry_id, None)
