"""Helperclass for ConfigEntry."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

type HausbusConfigEntry = ConfigEntry[HausbusConfig]


@dataclass
class HausbusConfig:
    """Class for Hausbus ConfigEntry."""

    from .gateway import HausbusGateway  # pylint: disable=import-outside-toplevel

    gateway: HausbusGateway
