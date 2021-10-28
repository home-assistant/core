"""Reusable utilities for the Rest component."""
from __future__ import annotations

from homeassistant.helpers.template import Template


def render_template(tpl_list: dict[str, Template] | None):
    """Render a dict of templates."""
    rendered_items = None
    if tpl_list:
        rendered_items = {}
        for item_name, template_header in tpl_list.items():
            if (value := template_header.async_render()) is not None:
                rendered_items[item_name] = value
    return rendered_items
