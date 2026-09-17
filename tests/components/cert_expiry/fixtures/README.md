# cert_expiry test fixtures

Checked-in certificates served by the local TLS servers built with `../cert_helpers.py`.
Nothing here is read from the network, and none of the keys are secret.

## Layout

- `root_ca.pem`, `root_ca.key.pem`: test root CA. `test_certs.py`'s `trust_test_ca`
  fixture points the default SSL context at it.
- `intermediate_ca.pem`, `intermediate_ca.key.pem`: intermediate CA signed by the root.
- `scenarios/<name>/`: one leaf certificate per scenario, as `cert.pem` (leaf plus
  any chain served with it), `key.pem` and `metadata.json` (the parameters the
  cert was built with, which tests assert against).
- `dh_params.pem`: see below.

## Regenerating

From the repository root:

```
python3 -m tests.components.cert_expiry.fixtures.generate
```

This rewrites the CAs and every scenario, so all fixtures change together.
Commit the whole result.

## Adding a scenario

1. Add a `_write_scenario("<name>", <issuer>, <key factory>, ...)` call to
   `main()` in `generate.py`. Add a new credential factory there if the
   scenario needs a different certificate shape.
2. Regenerate.
3. Load it in a test with `load_scenario("<name>")` from `../cert_helpers.py`
   and serve it with `local_tls_server(server_context(...))`.

## dh_params.pem

Diffie-Hellman parameters loaded by `server_context` in `../cert_helpers.py`.
Python's `ssl` server can't negotiate `DHE-*` cipher suites without them. The
`cipher_outside_intermediate_list` test relies on this: it serves only
`DHE-RSA-CHACHA20-POLY1305`, which the `INTERMEDIATE` cipher list doesn't allow.

It is not produced by `generate.py`. To regenerate it:

```
openssl dhparam -dsaparam -out dh_params.pem 2048
```

`-dsaparam` makes generation take seconds instead of minutes. That's fine here
because the parameters only need to be valid, not strong.
