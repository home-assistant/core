"""Init file for Home Assistant."""

from probatio import BuildPolicy, set_build_policy
from probatio.compat import install_as_voluptuous

# Probatio replaces voluptuous as the validation engine. Custom integrations and a
# few dependencies still import voluptuous directly, so alias it to probatio in
# sys.modules before anything imports it. This must run before the first
# `import voluptuous`, hence the package __init__.
install_as_voluptuous()

# Defer schema compilation until a schema is first validated. Home Assistant builds
# a large number of schemas, many of which are never validated in a given run, so
# lazy building avoids that upfront cost. Only the application may set this policy.
set_build_policy(BuildPolicy.LAZY)
