FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

# Initialize the submodules.
#Can't use git submodule init because we are not in a git repo anymore
RUN git clone https://github.com/balloob/pywemo.git external/pywemo && \
	git clone https://github.com/balloob/pynetgear.git external/pynetgear

VOLUME /config

EXPOSE 8123

CMD [ "python", "./start.py", "--docker" ]
