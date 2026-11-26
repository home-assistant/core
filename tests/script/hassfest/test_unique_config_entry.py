"""Tests for the hassfest unique-config-entry quality scale rule."""

from pathlib import Path

from hassfest.model import Config, Integration
import pytest

from script.hassfest.quality_scale_validation import unique_config_entry


@pytest.mark.parametrize(
    ("code", "valid"),
    [
        pytest.param(
            """
class FlowHandler(ConfigFlow):
    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("id")
        self._abort_if_unique_id_configured()
""",
            True,
            id="separate_checks",
        ),
        pytest.param(
            """
class FlowHandler(ConfigFlow):
    async def async_step_user(self, user_input=None):
        self._async_abort_entries_match({"host": "host"})
""",
            True,
            id="abort_entries_match",
        ),
        pytest.param(
            """
class FlowHandler(ConfigFlow):
    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id_or_abort("id")
""",
            True,
            id="helper_in_user_step",
        ),
        pytest.param(
            """
class FlowHandler(ConfigFlow):
    async def async_step_user(self, user_input=None):
        return self.async_create_entry(title="title", data={})
""",
            False,
            id="no_check",
        ),
        pytest.param(
            """
class FlowHandler(ConfigFlow):
    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("id")
        return self.async_create_entry(title="title", data={})

    async def async_step_reauth_confirm(self, user_input=None):
        await self.async_set_unique_id_or_abort("id")

    async def async_step_reconfigure(self, user_input=None):
        await self.async_set_unique_id_or_abort("id")
""",
            False,
            id="helper_only_in_reauth_and_reconfigure",
        ),
    ],
)
def test_unique_config_entry(
    tmp_path: Path, config: Config, code: str, valid: bool
) -> None:
    """Test which config flows prevent setting up a device twice."""
    (tmp_path / "config_flow.py").write_text(code)
    integration = Integration(tmp_path, _config=config, _manifest={})

    errors = unique_config_entry.validate(config, integration, rules_done=set())

    assert (errors is None) is valid
