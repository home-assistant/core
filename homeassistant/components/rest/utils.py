"""Reusable utilities for the Rest component."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template


def inject_hass_in_templates_list(
    hass: HomeAssistant, tpl_dict_list: list[dict[str, Template] | None]
):
    """Inject hass in a list of dict of templates."""
    for tpl_dict in tpl_dict_list:
        if tpl_dict is not None:
            for tpl in tpl_dict.values():
                tpl.hass = hass


def render_templates(tpl_dict: dict[str, Template] | None):
    """Render a dict of templates."""
    if tpl_dict is None:
        return None

    rendered_items = {}
    for item_name, template_header in tpl_dict.items():
        if (value := template_header.async_render()) is not None:
            rendered_items[item_name] = value
    return rendered_items
