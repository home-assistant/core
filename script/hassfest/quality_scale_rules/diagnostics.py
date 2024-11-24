"""Enforce that the integration has a reconfiguration flow."""

from . import QualityScaleCheck


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration has a reconfiguration flow."""

    diagnostics_file = check.integration.path / "diagnostics.py"
    if not diagnostics_file.exists():
        check.add_error(
            "diagnostics",
            "Integration does implement diagnostics platform (is missing diagnostics.py)",
        )
