FROM ghcr.io/dataresearchcenter/libpostal:main

RUN apt-get update && apt-get -y upgrade && \
    apt-get clean && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app/ftm-geocode

# Copy dependency files first for better layer caching
COPY pyproject.toml setup.py VERSION README.md ./

# Install dependencies (this layer is cached unless pyproject.toml changes)
RUN pip install --no-cache-dir -U pip setuptools && \
    pip install --no-cache-dir ".[postal]"

# Copy source code and data last (changes here don't invalidate dependency cache)
COPY ftm_geocode ./ftm_geocode
COPY data ./data

ENV PROCRASTINATE_APP="ftm_geocode.tasks.app"

USER 1000
ENTRYPOINT ["ftmgeo"]
