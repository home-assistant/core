"""Shared utilities for the decora_wifi platform."""

from __future__ import annotations

from enum import Enum, auto
import logging
from typing import Any

# pylint: disable=import-error
from decora_wifi import DecoraWiFiSession
from decora_wifi.models.iot_switch import IotSwitch
from decora_wifi.models.person import Person
from decora_wifi.models.residence import Residence
from decora_wifi.models.residential_account import ResidentialAccount

from homeassistant.components import persistent_notification
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "leviton_notification"
NOTIFICATION_TITLE = "myLeviton Decora Setup"


class BaseDecoraWifiEntity(Entity):
    """Encapsulates common functionality for all Decora Wifi switches."""

    def __init__(self, switch: IotSwitch) -> None:
        """Initialize BaseDecoraWifiEntity."""
        self._switch = switch
        self._attr_unique_id = str(switch.id)

    @property
    def name(self) -> str:
        """Get the switch's name."""

        return str(self._switch.name)

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""

        return str(self._switch.power) == "ON"

    def turn_off(self, **kwargs: dict[str, Any]) -> None:
        """Turn the switch off."""

        attribs = {"power": "OFF"}
        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn off myLeviton switch")

    def update(self) -> None:
        """Fetch the switch's current state."""

        try:
            self._switch.refresh()
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data")


class EntityTypes(Enum):
    """Supported Decora WiFi entity types."""

    LIGHT = auto()
    FAN = auto()


def _setup_platform(
    entity_type: EntityTypes,
    model: type[BaseDecoraWifiEntity],
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    email = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    session = DecoraWiFiSession()

    try:
        success = session.login(email, password)

        # If login failed, notify user.
        if success is None:
            msg = "Failed to log into myLeviton Services. Check credentials."
            _LOGGER.error(msg)
            persistent_notification.create(
                hass, msg, title=NOTIFICATION_TITLE, notification_id=NOTIFICATION_ID
            )
            return

        # Gather all the available devices...
        perms = session.user.get_residential_permissions()
        all_switches = []
        for permission in perms:
            if permission.residentialAccountId is not None:
                acct = ResidentialAccount(session, permission.residentialAccountId)
                for residence in acct.get_residences():
                    for switch in residence.get_iot_switches():
                        all_switches.append(switch)
            elif permission.residenceId is not None:
                residence = Residence(session, permission.residenceId)
                for switch in residence.get_iot_switches():
                    all_switches.append(switch)

        switches = filter(
            None,
            [map_switch_type(entity_type, model, sw) for sw in all_switches],
        )
        add_entities(switches)
    except ValueError:
        _LOGGER.error("Failed to communicate with myLeviton Service")

    # Listen for the stop event and log out.
    def logout(event: Event) -> None:
        try:
            if session is not None:
                Person.logout(session)
        except ValueError:
            _LOGGER.error("Failed to log out of myLeviton Service")

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, logout)


def map_switch_type(
    entity_type: EntityTypes, model: type[BaseDecoraWifiEntity], switch: IotSwitch
) -> BaseDecoraWifiEntity | None:
    """Map decora_wifi's IotSwitch type to custom types as appropriate."""

    fan_models = ["DW4SF"]
    if entity_type == EntityTypes.FAN and switch.model in fan_models:
        return model(switch)
    if entity_type == EntityTypes.LIGHT and switch.model not in fan_models:
        return model(switch)
    return None
