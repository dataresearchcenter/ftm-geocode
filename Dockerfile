FROM ghcr.io/investigativedata/libpostal:main

RUN apt-get update && apt-get -y upgrade

COPY ftm_geocode /app/ftm-geocode/ftm_geocode
COPY data /app/ftm-geocode/data
COPY setup.py /app/ftm-geocode/
COPY pyproject.toml /app/ftm-geocode/
COPY README.md /app/ftm-geocode/
COPY VERSION /app/ftm-geocode/

WORKDIR /app/ftm-geocode
RUN pip install -U pip setuptools
RUN pip install ".[postal]"
