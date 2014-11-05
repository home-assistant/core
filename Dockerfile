FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

VOLUME /config

EXPOSE 8123

CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
