"""Support for Obihai Sensors."""
from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass
import datetime

from requests.exceptions import RequestException

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .connectivity import ObihaiConnection
from .const import DOMAIN, LOGGER
from .entity import ObihaiEntity

SCAN_INTERVAL = datetime.timedelta(seconds=5)


class ObihaiSensor(ObihaiEntity, SensorEntity, ABC):
    """Generic Obihai Sensor."""

    def __init__(
        self,
        requester: ObihaiConnection,
        service_name: str,
        entity_description: ObihaiSensorEntityDescription,
    ) -> None:
        """Obihai Sensors have an EntityDescription, store it and then setup a generic ObihaiEntity."""
        self.entity_description = entity_description
        super().__init__(requester, service_name)

    @property
    def icon(self) -> str:
        """Return an icon."""
        return self.entity_description.icon_fn(self)

    def update(self) -> None:
        """Update the sensor."""

        LOGGER.debug("Running update on %s", self.service_name)
        try:
            self._attr_native_value = self.entity_description.update_fn(self)

            if not self.requester.available:
                self.requester.available = True
                LOGGER.info("Connection restored")
            self._attr_available = True

            return

        except RequestException as exc:
            if self.requester.available:
                LOGGER.warning("Connection failed, Obihai offline? %s", exc)
        except IndexError as exc:
            if self.requester.available:
                LOGGER.warning("Connection failed, bad response: %s", exc)

        self._attr_native_value = None
        self._attr_available = False
        self.requester.available = False


# TODO: This didn't really improve anything, now we have these loose callables IN ADDITION to the EntityDescriptions...
class ObihaiCallDirectionSensor:
    """Call Direction sensor."""

    @staticmethod
    def icon(entity: ObihaiSensor) -> str:
        """Return an icon."""

        if entity.state == "No Active Calls":
            return "mdi:phone-off"
        if entity.state == "Inbound Call":
            return "mdi:phone-incoming"
        return "mdi:phone-outgoing"

    @staticmethod
    def update(entity: ObihaiSensor) -> str | None:
        """Update the sensor."""
        call_direction = entity.pyobihai.get_call_direction()

        if entity.service_name in call_direction:
            return call_direction.get(entity.service_name)
        return None


class ObihaiLineServiceSensor:
    """PHONE1 Port/PHONE1 Port last caller info sensors."""

    @staticmethod
    def icon(entity: ObihaiSensor) -> str:
        """Return an icon."""
        if entity.state == "Ringing":
            return "mdi:phone-ring"
        if entity.state == "Off Hook":
            return "mdi:phone-in-talk"
        return "mdi:phone-hangup"

    @staticmethod
    def update(entity: ObihaiSensor) -> str | None:
        """Update the sensor."""
        services = entity.pyobihai.get_line_state()

        if services is not None and entity.service_name in services:
            return services.get(entity.service_name)
        return None


class ObihaiServiceSensor:
    """Reboot Required/Last Reboot/SP Service Status/OBiTALK Service Status sensors."""

    @staticmethod
    def icon(entity: ObihaiSensor) -> str:
        """Return an icon."""

        if "Service Status" in entity.service_name:
            if "OBiTALK Service Status" in entity.service_name:
                return "mdi:phone-check"
            if entity.state == "0":
                return "mdi:phone-hangup"
            return "mdi:phone-in-talk"
        if "Reboot Required" in entity.service_name:
            if entity.state == "false":
                return "mdi:restart-off"
            return "mdi:restart-alert"
        return "mdi:phone"

    @staticmethod
    def update(entity: ObihaiSensor) -> str | None:
        """Update the sensor."""

        services = entity.pyobihai.get_state()

        if entity.service_name in services:
            return services.get(entity.service_name)
        return None


# TODO: mypy doesn't like these, says SensorEntityDescription doesn't have these attr...
@dataclass
class ObihaiSensorEntityDescriptionMixin:
    """Mixin for required Obihai base description keys."""

    icon_fn: Callable[[ObihaiSensor], StateType]
    update_fn: Callable[[ObihaiSensor], StateType | None]


@dataclass
class ObihaiSensorEntityDescription(
    SensorEntityDescription, ObihaiSensorEntityDescriptionMixin
):
    """Describes Obihai sensor entity."""


OBIHAI_CALL_DIRECTION_ENTITY_DESCRIPTION = ObihaiSensorEntityDescription(
    key="call_direction",
    icon_fn=ObihaiCallDirectionSensor.icon,
    update_fn=ObihaiCallDirectionSensor.update,
)


def obihai_line_services_entity_description(key: str) -> ObihaiSensorEntityDescription:
    """Variable number of line services depending on OBihai model.

    Typically 1-2.  Here we dynamically generate EntityDescriptions with unique keys.
    """
    new_key = "_".join(key.lower().split())
    icon_lambda = lambda _: "mdi:phone-log"
    icon_fn = icon_lambda if "Caller Info" in key else ObihaiLineServiceSensor.icon

    return ObihaiSensorEntityDescription(
        key=new_key,
        icon_fn=icon_fn,
        update_fn=ObihaiLineServiceSensor.update,
    )


def obihai_service_entity_description(key: str) -> ObihaiSensorEntityDescription:
    """Different Obihai models have support for varying numbers of SIPs.

    Obi100 has 1, Obi200 has 4, etc. Here we dynamically generate EntityDescriptions with unique keys.
    """
    new_key = "_".join(key.lower().split())
    device_class = SensorDeviceClass.TIMESTAMP if "Last Reboot" in key else None

    return ObihaiSensorEntityDescription(
        key=new_key,
        device_class=device_class,
        icon_fn=ObihaiServiceSensor.icon,
        update_fn=ObihaiServiceSensor.update,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Obihai sensor entries."""

    requester: ObihaiConnection = hass.data[DOMAIN][entry.entry_id]

    sensors: list[ObihaiEntity] = []
    for key in requester.services:
        sensors.append(
            ObihaiSensor(requester, key, obihai_service_entity_description(key))
        )

    if requester.line_services is not None:
        for key in requester.line_services:
            sensors.append(
                ObihaiSensor(
                    requester, key, obihai_line_services_entity_description(key)
                )
            )

    for key in requester.call_direction:
        sensors.append(
            ObihaiSensor(requester, key, OBIHAI_CALL_DIRECTION_ENTITY_DESCRIPTION)
        )

    async_add_entities(sensors, update_before_add=True)
