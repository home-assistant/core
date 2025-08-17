# Run all vitrea tests with coverage
pytest ./tests/components/vitrea \
  --cov=homeassistant.components.vitrea \
  --cov-report term-missing \
  --durations-min=1 \
  --numprocesses=auto

# Run specific test files
pytest ./tests/components/vitrea/test_switch.py -v
pytest ./tests/components/vitrea/test_config_flow.py -v
pytest ./tests/components/vitrea/test_init.py -v
pytest ./tests/components/vitrea/test_setup.py -v
pytest ./tests/components/vitrea/test_switch.py -v --cov=homeassistant.components.vitrea.switch
pytest ./tests/components/vitrea/test_config_flow.py -v --cov=homeassistant.components.vitrea.config_flow
pytest ./tests/components/vitrea/test_init.py -v --cov=homeassistant.components.v
# pytest ./tests/components/vitrea/test_setup.py -v --cov=homeassistant.components.vitrea.setup
pytest ./tests/components/vitrea/test_setup.py -v --cov=homeassistant.components.vitrea.setup
# pytest ./tests/components/vitrea/test_switch.py -v --cov=homeassistant.components.vitrea.switch
pytest ./tests/components/vitrea/test_switch.py -v --cov=homeassistant.components.v
# vitrea.switch
pytest ./tests/components/vitrea/test_config_flow.py -v --cov=homeassistant.components.vitrea.config_flow
pytest ./tests/components/vitrea/test_init.py -v --cov=homeassistant.components.v
# vitrea.init
pytest ./tests/components/vitrea/test_setup.py -v --cov=homeassistant.components.vitrea.setup
pytest ./tests/components/vitrea/test_init.py -v --cov=homeassistant.components.vitrea.init
# pytest ./tests/components/vitrea/test_setup.py -v --cov=homeassistant.components.vitrea.setup
pytest ./tests/components/vitrea/test_setup.py -v --cov=homeassistant.components.vitrea.setup
# pytest ./tests/components/vitrea/test_switch.py -v --cov=homeassistant.components.vitrea.switch
pytest ./tests/components/vitrea/test_switch.py -v --cov=homeassistant.components.vitrea.switch
# vitrea.switch
pytest ./tests/components/vitrea/test_config_flow.py -v --cov=homeassistant.components.vitrea.config_flow
pytest ./tests/components/vitrea/test_init.py -v --cov=homeassistant.components.vitrea.init
# vitrea.init
pytest ./tests/components/vitrea/test_setup.py -v --cov=homeassistant.components.vitrea.setup
pytest ./tests/components/vitrea/test_switch.py -v --cov=homeassistant.components.vitrea.switch
# vitrea.switch

