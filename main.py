"""Main entry point for the EPUB Translator application."""

import sys
import logging
from pathlib import Path
from PyQt5.QtWidgets import QApplication

from src.translator.ui import EpubTranslatorApp
from src.translator.utils.logging_config import setup_logging


def main():
    """Run the EPUB Translator application.

    Initializes logging and launches the PyQt5 GUI.
    """
    # Setup logging
    log_dir = Path.home() / ".epub-translator" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "translator.log"

    setup_logging(
        log_file=str(log_file),
        level=logging.INFO,
        console=True
    )

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("EPUB Translator Application Starting")
    logger.info("=" * 60)

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("EPUB Translator")
        app.setOrganizationName("EPUB-Translator")

        window = EpubTranslatorApp()
        window.show()

        logger.info("Application window displayed successfully")

        exit_code = app.exec_()

        logger.info(f"Application exiting with code: {exit_code}")
        sys.exit(exit_code)

    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
