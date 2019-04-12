"""Models for manifest validator."""
import json
import pathlib

import attr


@attr.s
class Integration:
    """Represent an integration in our validator."""

    path = attr.ib(type=pathlib.Path)
    manifest = attr.ib(type=dict, default=None)
    errors = attr.ib(type=list, factory=list)

    @property
    def domain(self):
        """Integration domain."""
        return self.path.name

    @property
    def manifest_path(self):
        """Integration manifest path."""
        return self.path / 'manifest.json'

    @property
    def dependencies(self):
        """Get dependencies."""
        return [] if self.manifest is None else self.manifest['dependencies']

    def load_manifest(self):
        """Load manifest."""
        if not self.manifest_path.is_file():
            self.errors.append(
                "Manifest file {} not found".format(self.manifest_path))
            return

        try:
            manifest = json.loads(self.manifest_path.read_text())
        except ValueError as err:
            self.errors.append(
                "Manifest contains invalid JSON: {}".format(err))
            return

        self.manifest = manifest
