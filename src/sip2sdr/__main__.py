"""CLI entry point for sip2sdr."""

from __future__ import annotations

import argparse
import logging
import signal
import time
from pathlib import Path

from sip2sdr.audio.ring_buffer import RingBuffer
from sip2sdr.audio.tts import TtsEngine
from sip2sdr.channels import ChannelMode
from sip2sdr.config import load_config
from sip2sdr.sdr.flowgraph import SdrFlowgraph
from sip2sdr.sip.engine import SipEngine
from sip2sdr.utils.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse arguments and start the SIP2SDR application."""
    parser = argparse.ArgumentParser(
        description="SIP2SDR — stream Marine VHF radio to SIP callers"
    )
    parser.add_argument("config", help="Path to YAML config file")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    args = parser.parse_args()

    configure_logging(args.log_level)

    cfg = load_config(Path(args.config))
    logger.info("Loaded config: mode=%s", cfg.mode.value)

    n = len(cfg.sip.extensions)
    buffers = [RingBuffer(capacity=cfg.audio.buffer_size) for _ in range(n)]

    tts_cache = Path("/tmp/sip2sdr_tts")  # noqa: S108
    tts = TtsEngine(cache_dir=tts_cache)
    tts.prewarm(channels=list(range(1, 89 if cfg.mode == ChannelMode.MARINE else 70)))

    fg = SdrFlowgraph(
        mode=cfg.mode,
        sdr_device_args=f"{cfg.sdr.device}=0",
        sample_rate=cfg.sdr.sample_rate,
        gain_lna=cfg.sdr.gain_lna,
        gain_vga=cfg.sdr.gain_vga,
        gain_amp=cfg.sdr.gain_amp,
        initial_channels=[e.default_channel for e in cfg.sip.extensions],
        buffers=buffers,
    )

    def _make_retune(idx: int):  # noqa: ANN202
        return lambda ch: fg.retune(idx, ch)

    retune_fns = [_make_retune(i) for i in range(n)]

    sip = SipEngine(
        sip_config=cfg.sip,
        buffers=buffers,
        retune_fns=retune_fns,
        mode=cfg.mode,
    )

    fg.start()
    sip.start()
    logger.info("SIP2SDR running — press Ctrl+C to stop")

    stop_event = [False]

    def _sighandler(sig: int, frame: object) -> None:
        stop_event[0] = True

    signal.signal(signal.SIGINT, _sighandler)
    signal.signal(signal.SIGTERM, _sighandler)

    while not stop_event[0]:
        time.sleep(0.5)

    logger.info("Shutting down…")
    sip.stop()
    fg.stop()
    fg.wait()


if __name__ == "__main__":
    main()
