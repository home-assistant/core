"""Workarounds."""

from aiogithubapi.models.git_tree import GitHubGitTreeEntryModel

DOMAIN_OVERRIDES: dict[str, str] = {
    # https://github.com/hacs/integration/issues/2465
    "custom-components/sensor.custom_aftership": "custom_aftership"
}


class LegacyTreeFile:
    """Legacy TreeFile representation.

    This serves as a compatibility layer for code expecting
    the older TreeFile structure.
    """

    def __init__(
        self, model: GitHubGitTreeEntryModel, repository: str, ref: str | None
    ) -> None:
        """Initialize."""
        self.model = model
        self.repository = repository
        self.ref = ref

        # Simple calculated attributes
        self.full_path = self.model.path
        self.is_directory = self.model.type == "tree"
        self.url = self.model.url
        self.download_url = f"https://raw.githubusercontent.com/{self.repository}/{self.ref}/{self.full_path}"

    @property
    def path(self) -> str:
        """Return the path of the parent directory."""
        path = ""
        if "/" in self.full_path:
            path = self.full_path.split(f"/{self.full_path.split('/')[-1]}")[0]
        return path

    @property
    def filename(self) -> str:
        """Return the filename without the directories."""
        filename = self.full_path
        if "/" in self.full_path:
            filename = self.full_path.split("/")[-1]
        return filename
