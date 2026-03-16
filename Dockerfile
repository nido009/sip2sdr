FROM debian:bookworm-slim

# Install all system dependencies in a single layer to keep image lean
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnuradio \
    gr-osmosdr \
    python3-pjsua2 \
    libpjproject-dev \
    hackrf \
    espeak-ng \
    python3 \
    python3-pip \
 && rm -rf /var/lib/apt/lists/*

# GNU Radio Python bindings are installed into system site-packages, not pip-installable
ENV PYTHONPATH=/usr/lib/python3/dist-packages

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

# Install app pip deps into the system Python (container is the isolation boundary)
RUN pip install --break-system-packages -e .

# Config is provided at runtime via volume mount
CMD ["python3", "-m", "sip2sdr", "-c", "/config/config.yaml"]
