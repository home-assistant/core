import betamax

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = 'tests/cassettes'
