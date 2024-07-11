"""Tests for the Azure DevOps integration."""

from typing import Final

from aioazuredevops.models.builds import Build, BuildDefinition
from aioazuredevops.models.core import Project

from homeassistant.components.azure_devops.const import CONF_ORG, CONF_PAT, CONF_PROJECT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ORGANIZATION: Final[str] = "testorg"
PROJECT: Final[str] = "testproject"
PAT: Final[str] = "abc123"

UNIQUE_ID = f"{ORGANIZATION}_{PROJECT}"


FIXTURE_USER_INPUT = {
    CONF_ORG: ORGANIZATION,
    CONF_PROJECT: PROJECT,
    CONF_PAT: PAT,
}

FIXTURE_REAUTH_INPUT = {
    CONF_PAT: PAT,
}


DEVOPS_PROJECT = Project(
    id="1234",
    name=PROJECT,
    description="Test Description",
    url=f"https://dev.azure.com/{ORGANIZATION}/{PROJECT}",
    state="wellFormed",
    revision=1,
    visibility="private",
    default_team=None,
    links=None,
)

DEVOPS_BUILD_DEFINITION = BuildDefinition(
    build_id=9876,
    name="CI",
    url=f"https://dev.azure.com/{ORGANIZATION}/{PROJECT}/_apis/build/definitions/1",
    path="",
    build_type="build",
    queue_status="enabled",
    revision=1,
)

DEVOPS_BUILD = Build(
    build_id=5678,
    build_number="1",
    status="completed",
    result="succeeded",
    source_branch="main",
    source_version="123",
    priority="normal",
    reason="manual",
    queue_time="2021-01-01T00:00:00Z",
    start_time="2021-01-01T00:00:00Z",
    finish_time="2021-01-01T00:00:00Z",
    definition=DEVOPS_BUILD_DEFINITION,
    project=DEVOPS_PROJECT,
    links=None,
)

DEVOPS_BUILD_MISSING_DATA = Build(
    build_id=6789,
    definition=DEVOPS_BUILD_DEFINITION,
    project=DEVOPS_PROJECT,
)

DEVOPS_BUILD_MISSING_PROJECT_DEFINITION = Build(
    build_id=9876,
)


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> bool:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return result
