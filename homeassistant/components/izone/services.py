"""Services for the iZone integration."""

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir, service
from homeassistant.helpers.typing import VolDictType

from .const import ATTR_AIRFLOW, DOMAIN

IZONE_SERVICE_AIRFLOW_MIN = "airflow_min"
IZONE_SERVICE_AIRFLOW_MAX = "airflow_max"
IZONE_SERVICE_AIRFLOW_SCHEMA: VolDictType = {
    probatio.Required(ATTR_AIRFLOW): probatio.All(
        probatio.Coerce(float),
        probatio.In(range(0, 101, 5)),
        probatio.Coerce(int),
        msg="invalid airflow",
    ),
}


@callback
def async_create_deprecated_airflow_issue(
    hass: HomeAssistant, service_name: str
) -> None:
    """Point users of a deprecated airflow action at the damper number entities."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_action_{service_name}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_airflow_action",
        translation_placeholders={"action": f"{DOMAIN}.{service_name}"},
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the iZone integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        IZONE_SERVICE_AIRFLOW_MIN,
        entity_domain=CLIMATE_DOMAIN,
        schema=IZONE_SERVICE_AIRFLOW_SCHEMA,
        func="async_set_airflow_min",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        IZONE_SERVICE_AIRFLOW_MAX,
        entity_domain=CLIMATE_DOMAIN,
        schema=IZONE_SERVICE_AIRFLOW_SCHEMA,
        func="async_set_airflow_max",
    )
