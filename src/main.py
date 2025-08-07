#!/usr/bin/env python3
"""
Widget Window Spy - Main Application Entry Point

A professional screenshot analysis tool that provides pixel-perfect coordinate tracking,
visualization, and bbox management for automation development.

Usage:
    python main.py [--target PROCESS_NAME]
"""

import argparse
import logging
import signal
import sys

from PyQt6.QtWidgets import QApplication

from core.constants import LOG_LEVEL, LOG_FORMAT, TARGET_PROCESS_DEFAULT
from ui.tracker_widget import TrackerWidget


def setup_logging() -> logging.Logger:
    """Setup application logging."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT,
    )
    return logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Widget Window Spy - Professional coordinate tracking tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                          # Track default WidgetInc.exe
    python main.py --target MyApp.exe       # Track custom application

Features:
    - Real-time coordinate tracking across multiple coordinate systems
    - Professional screenshot viewer with bbox editing
    - Grid overlay and zoom functionality
    - Clipboard integration for coordinate copying
    - Freeze functionality (Ctrl+F) for static coordinate capture
        """,
    )

    parser.add_argument(
        "--target",
        default=TARGET_PROCESS_DEFAULT,
        help=f"Target process name to track (default: {TARGET_PROCESS_DEFAULT})",
        metavar="PROCESS",
    )

    parser.add_argument("--version", action="version", version="Widget Window Spy v1.0")

    return parser.parse_args()


def setup_signal_handlers(tracker: TrackerWidget, app: QApplication) -> None:
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down gracefully...")
        tracker.close()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main() -> int:
    """Main application entry point."""
    # Parse arguments and setup logging
    args = parse_arguments()
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info("Widget Window Spy - Starting Application")
    logger.info("=" * 60)
    logger.info(f"Target process: {args.target}")

    try:
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("Widget Window Spy")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("Widget Automation Tools")

        # Create main tracker widget
        tracker = TrackerWidget(args.target)

        # Setup signal handlers for graceful shutdown
        setup_signal_handlers(tracker, app)

        # Show tracker and start event loop
        tracker.show()
        logger.info("Application started successfully")

        return app.exec()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        return 1
    finally:
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    sys.exit(main())
