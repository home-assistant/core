FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

# Initialize the submodules
RUN git submodule init && git submodule update --recursive

VOLUME /config

EXPOSE 8123

CMD [ "python", "./start.py", "--docker" ]
