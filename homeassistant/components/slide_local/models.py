"""Dataclass models for the slide_local integration."""

from dataclasses import dataclass

from goslideapi import GoSlideLocal as SlideLocalApi

from homeassistant.config_entries import ConfigEntry

type SlideConfigEntry = ConfigEntry[SlideData]


@dataclass
class SlideData:
    """Data for the slide_local integration."""

    api: SlideLocalApi
    api_version: int
    host: str
    mac: str
    password: str
