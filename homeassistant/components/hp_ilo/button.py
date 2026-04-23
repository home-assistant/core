"""Support for HP iLO buttons."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import hpilo
import voluptuous as vol

from homeassistant.components.button import (
    PLATFORM_SCHEMA as BUTTON_PLATFORM_SCHEMA,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "HP ILO"
DEFAULT_PORT = 443

PLATFORM_SCHEMA = BUTTON_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


@dataclass(frozen=True, kw_only=True)
class HpIloButtonEntityDescription(ButtonEntityDescription):
    """Describes an HP iLO button entity."""

    ilo_method: str
    ilo_method_kwargs: dict | None = None


BUTTON_TYPES: tuple[HpIloButtonEntityDescription, ...] = (
    HpIloButtonEntityDescription(
        key="power_on",
        name="Power On",
        ilo_method="set_host_power",
        ilo_method_kwargs={"host_power": True},
    ),
    HpIloButtonEntityDescription(
        key="power_off",
        name="Power Off",
        ilo_method="set_host_power",
        ilo_method_kwargs={"host_power": False},
    ),
    HpIloButtonEntityDescription(
        key="press_power_button",
        name="Press Power Button",
        ilo_method="press_pwr_btn",
    ),
    HpIloButtonEntityDescription(
        key="cold_boot",
        name="Cold Boot",
        device_class=ButtonDeviceClass.RESTART,
        ilo_method="cold_boot_server",
    ),
    HpIloButtonEntityDescription(
        key="warm_boot",
        name="Warm Boot",
        device_class=ButtonDeviceClass.RESTART,
        ilo_method="warm_boot_server",
    ),
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HP iLO button platform."""
    hostname = config[CONF_HOST]
    port = config[CONF_PORT]
    login = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    name = config[CONF_NAME]

    add_entities(
        HpIloButton(
            description=description,
            name=f"{name} {description.name}",
            hostname=hostname,
            port=port,
            login=login,
            password=password,
        )
        for description in BUTTON_TYPES
    )


class HpIloButton(ButtonEntity):
    """Representation of an HP iLO button."""

    entity_description: HpIloButtonEntityDescription

    def __init__(
        self,
        description: HpIloButtonEntityDescription,
        name: str,
        hostname: str,
        port: int,
        login: str,
        password: str,
    ) -> None:
        """Initialize the HP iLO button."""
        self.entity_description = description
        self._attr_name = name
        self._hostname = hostname
        self._port = port
        self._login = login
        self._password = password

    def press(self) -> None:
        """Execute the button action via HP iLO."""
        try:
            ilo = hpilo.Ilo(
                hostname=self._hostname,
                login=self._login,
                password=self._password,
                port=self._port,
            )
            method = getattr(ilo, self.entity_description.ilo_method)
            kwargs = self.entity_description.ilo_method_kwargs or {}
            method(**kwargs)
        except (
            hpilo.IloError,
            hpilo.IloCommunicationError,
            hpilo.IloLoginFailed,
        ) as error:
            _LOGGER.error("Unable to perform HP iLO action: %s", error)
