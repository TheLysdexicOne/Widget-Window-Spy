"""Launcher script for Widget Window Spy (modular version).

This replaces the monolithic entrypoint. It wires up logging, argument parsing,
creates the QApplication, and launches the TrackerWidget from the tracker package.
"""

from __future__ import annotations

import sys
import signal
import argparse
import logging
from PyQt6.QtWidgets import QApplication

from tracker.tracker_widget import TrackerWidget


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger("widget_window_spy")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Widget Window Spy")
    parser.add_argument(
        "--target",
        default="WidgetInc.exe",
        help="Target process name to track (default: WidgetInc.exe)",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    logger = setup_logging()
    logger.info(f"Starting tracker for {args.target}")

    app = QApplication(sys.argv)
    tracker = TrackerWidget(args.target)
    tracker.show()

    def signal_handler(signum, frame):  # noqa: D401, unused params required by signal
        logger.info("Shutdown signal received")
        tracker.close()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
