FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gnuradio \
    gr-osmosdr \
    python3-pjsua2 \
    libpjproject-dev \
    hackrf \
    espeak-ng \
    python3 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/usr/lib/python3/dist-packages
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/

RUN uv pip install --system --break-system-packages -e .

CMD ["python3", "-m", "sip2sdr", "-c", "/config/config.yaml"]
