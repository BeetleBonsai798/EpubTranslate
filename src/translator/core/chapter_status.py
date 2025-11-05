"""Chapter status tracking for translation progress."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ChapterStatus:
    """Tracks the translation status and metadata for a single chapter.

    Attributes:
        chapter_number: The chapter number
        title: The chapter title
        status: Translation status ("Not Started", "In Progress", "Completed")
        xhtml_exists: Whether the translated XHTML file exists
        xhtml_path: Path to the translated XHTML file
        file_size: Size of the translated file in bytes
        last_modified: Timestamp of last modification
    """

    def __init__(self, chapter_number: int, title: str = ""):
        """Initialize chapter status.

        Args:
            chapter_number: The chapter number
            title: The chapter title (optional)
        """
        self.chapter_number = chapter_number
        self.title = title
        self.status = "Not Started"
        self.xhtml_exists = False
        self.xhtml_path = ""
        self.file_size = 0
        self.last_modified = ""

    def update_status(self, xhtml_path: str = "") -> None:
        """Update status based on XHTML file existence.

        Args:
            xhtml_path: Path to the translated XHTML file
        """
        self.xhtml_path = xhtml_path

        if not xhtml_path:
            self.xhtml_exists = False
            self.status = "Not Started"
            return

        path = Path(xhtml_path)
        self.xhtml_exists = path.exists()

        if self.xhtml_exists:
            self.status = "Completed"
            try:
                stat = path.stat()
                self.file_size = stat.st_size
                self.last_modified = datetime.fromtimestamp(stat.st_mtime).strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
                logger.debug(
                    f"Chapter {self.chapter_number} status updated: "
                    f"{self.file_size} bytes, modified {self.last_modified}"
                )
            except OSError as e:
                logger.warning(
                    f"Could not read file stats for chapter {self.chapter_number}: {e}"
                )
        else:
            self.status = "Not Started"
            logger.debug(f"Chapter {self.chapter_number}: XHTML file not found at {xhtml_path}")
