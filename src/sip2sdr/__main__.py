"""CLI entry point for sip2sdr."""

import argparse
import sys


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
    print(f"SIP2SDR starting with config={args.config}, test_mode={args.test_mode}")
    sys.exit(0)


if __name__ == "__main__":
    main()
