"""Home Assistant scripts."""

import contextlib
from pathlib import Path
import sys

# Core scripts use the checkout's hassfest, even before package installation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages/hassfest"))

# Scripts such as hassfest (and the libraries they import) use voluptuous. Alias it
# to probatio before anything imports it, the same as homeassistant/__init__.py does
# for the application itself. This must run before the first `import voluptuous`.
# Some scripts (for example check_requirements) run before dependencies are
# installed, so probatio may be absent; those scripts do not need the alias.
with contextlib.suppress(ImportError):
    from probatio.compat import install_as_voluptuous

    install_as_voluptuous()
