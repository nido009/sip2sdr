"""CLI entry point for sip2sdr."""

import argparse
import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse arguments and start the SIP2SDR application."""
    parser = argparse.ArgumentParser(
        description="SIP2SDR — stream Marine VHF radio to SIP callers"
    )
    parser.add_argument("config", help="Path to YAML config file")
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Use LPD433 test band instead of Marine VHF",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logger.info("SIP2SDR starting with config=%s, test_mode=%s", args.config, args.test_mode)


if __name__ == "__main__":
    main()
