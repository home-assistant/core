"""ESPHome test common code."""

from homeassistant.components import assist_satellite
from homeassistant.components.assist_satellite import AssistSatelliteEntity

# pylint: disable-next=hass-component-root-import
from homeassistant.components.esphome import DOMAIN
from homeassistant.components.esphome.assist_satellite import EsphomeAssistSatellite
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent


def get_satellite_entity(
    hass: HomeAssistant, mac_address: str
) -> EsphomeAssistSatellite | None:
    """Get the satellite entity for a device."""
    ent_reg = er.async_get(hass)
    satellite_entity_id = ent_reg.async_get_entity_id(
        Platform.ASSIST_SATELLITE, DOMAIN, f"{mac_address}-assist_satellite"
    )
    if satellite_entity_id is None:
        return None
    assert satellite_entity_id.endswith("_assist_satellite")

    component: EntityComponent[AssistSatelliteEntity] = hass.data[
        assist_satellite.DOMAIN
    ]
    if (entity := component.get_entity(satellite_entity_id)) is not None:
        assert isinstance(entity, EsphomeAssistSatellite)
        return entity

    return None
