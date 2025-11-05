"""Chapter overview widget for tracking translation progress."""

import os
from typing import Dict
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog,
                             QProgressBar, QApplication)
from PySide6.QtGui import QFont, QColor

from ..core.chapter_status import ChapterStatus


class ChapterOverviewWidget(QWidget):
    """Widget to show chapter translation overview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.chapter_statuses: Dict[int, ChapterStatus] = {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()
        self.status_label = QLabel("No EPUB loaded")
        self.status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(self.status_label)

        # Chapter count label (separate from book title)
        self.chapter_count_label = QLabel("")
        self.chapter_count_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(self.chapter_count_label)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.clicked.connect(self.refresh_status)
        header_layout.addWidget(self.refresh_btn)

        # Build EPUB button
        self.build_epub_btn = QPushButton("Build EPUB")
        self.build_epub_btn.clicked.connect(self.build_epub)
        self.build_epub_btn.setEnabled(False)
        header_layout.addWidget(self.build_epub_btn)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Chapter table
        self.chapter_table = QTableWidget()
        self.chapter_table.setColumnCount(6)
        self.chapter_table.setHorizontalHeaderLabels([
            "Chapter", "Title", "Status", "File Size", "Last Modified", "Actions"
        ])

        # Set column widths
        self.chapter_table.setColumnWidth(0, 80)
        self.chapter_table.setColumnWidth(1, 300)
        self.chapter_table.setColumnWidth(2, 150)
        self.chapter_table.setColumnWidth(3, 100)
        self.chapter_table.setColumnWidth(4, 150)
        self.chapter_table.setColumnWidth(5, 200)

        layout.addWidget(self.chapter_table)
        self.setLayout(layout)

    def update_epub_info(self, epub_path: str, chapters: list, epub_name: str):
        """Update chapter information when EPUB is loaded."""
        self.epub_path = epub_path
        self.chapters = chapters
        self.epub_name = epub_name
        self.output_folder = os.path.join(os.path.dirname(__file__), "..", "..", "..", f"{epub_name}_translated")

        # Initialize chapter statuses
        self.chapter_statuses = {}
        for i, chapter in enumerate(chapters, 1):
            # Try to extract title from chapter content
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(chapter, 'html.parser')
            title = ""
            # Look for common title patterns
            for tag in ['h1', 'h2', 'title']:
                title_elem = soup.find(tag)
                if title_elem:
                    title = title_elem.get_text().strip()[:50]
                    break

            if not title:
                # Try to get first line as title
                text = soup.get_text().strip()
                if text:
                    first_line = text.split('\n')[0].strip()[:50]
                    if len(first_line) < 100:
                        title = first_line

            self.chapter_statuses[i] = ChapterStatus(i, title)

        self.status_label.setText(f"EPUB: {epub_name}")
        self.chapter_count_label.setText(f"Total Chapters: {len(chapters)}")
        self.refresh_status()

    def refresh_status(self):
        """Refresh the status of all chapters."""
        if not hasattr(self, 'output_folder'):
            return

        # Update status for each chapter
        for chapter_num, status in self.chapter_statuses.items():
            xhtml_path = os.path.join(self.output_folder, "xhtml", f"{chapter_num}.xhtml")
            status.update_status(xhtml_path)

        self.update_table()
        self.update_summary()

    def update_table(self):
        """Update the chapter table display."""
        self.chapter_table.setRowCount(len(self.chapter_statuses))

        for row, (chapter_num, status) in enumerate(self.chapter_statuses.items()):
            # Chapter number
            self.chapter_table.setItem(row, 0, QTableWidgetItem(str(chapter_num)))

            # Title
            title_item = QTableWidgetItem(status.title if status.title else f"Chapter {chapter_num}")
            self.chapter_table.setItem(row, 1, title_item)

            # Status
            status_item = QTableWidgetItem(status.status)
            # Color code the status with darker colors
            if status.status.startswith("Completed"):
                status_item.setBackground(QColor(34, 139, 34))
                status_item.setForeground(QColor(255, 255, 255))
            elif status.status == "In Progress":
                status_item.setBackground(QColor(184, 134, 11))
                status_item.setForeground(QColor(255, 255, 255))
            elif status.status == "Error":
                status_item.setBackground(QColor(178, 34, 34))
                status_item.setForeground(QColor(255, 255, 255))
            else:
                status_item.setBackground(QColor(70, 70, 70))
                status_item.setForeground(QColor(200, 200, 200))

            self.chapter_table.setItem(row, 2, status_item)

            # File size
            size_text = ""
            if status.file_size > 0:
                if status.file_size < 1024:
                    size_text = f"{status.file_size} B"
                elif status.file_size < 1024 * 1024:
                    size_text = f"{status.file_size / 1024:.1f} KB"
                else:
                    size_text = f"{status.file_size / (1024 * 1024):.1f} MB"
            self.chapter_table.setItem(row, 3, QTableWidgetItem(size_text))

            # Last modified
            self.chapter_table.setItem(row, 4, QTableWidgetItem(status.last_modified))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout()
            actions_layout.setContentsMargins(2, 2, 2, 2)

            if status.xhtml_exists:
                view_btn = QPushButton("View")
                view_btn.setMaximumWidth(50)
                view_btn.clicked.connect(lambda checked, path=status.xhtml_path: self.open_file(path))
                actions_layout.addWidget(view_btn)

            actions_layout.addStretch()
            actions_widget.setLayout(actions_layout)
            self.chapter_table.setCellWidget(row, 5, actions_widget)

    def update_summary(self):
        """Update summary information."""
        total = len(self.chapter_statuses)
        completed_xhtml = sum(1 for s in self.chapter_statuses.values() if s.xhtml_exists)
        not_started = total - completed_xhtml

        # Update labels separately
        self.status_label.setText(f"EPUB: {getattr(self, 'epub_name', 'None')}")
        self.chapter_count_label.setText(f"Translated: {completed_xhtml}/{total} chapters")
        
        # Enable build EPUB button ONLY if ALL chapters are translated
        all_chapters_translated = (completed_xhtml == total and total > 0)
        self.build_epub_btn.setEnabled(all_chapters_translated)
        
        if all_chapters_translated:
            self.build_epub_btn.setStyleSheet("QPushButton { background-color: #90EE90; font-weight: bold; }")
        else:
            self.build_epub_btn.setStyleSheet("")

    def open_file(self, file_path: str):
        """Open file with system default application."""
        try:
            import sys
            if os.name == 'nt':
                os.startfile(file_path)
            elif os.name == 'posix':
                os.system(f'open "{file_path}"' if sys.platform == 'darwin' else f'xdg-open "{file_path}"')
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {str(e)}")

    def build_epub(self):
        """Build final EPUB with TOC translation - only when all chapters are translated."""
        if not hasattr(self, 'epub_path') or not self.epub_path:
            QMessageBox.warning(self, "Warning", "No EPUB file loaded!")
            return
            
        if not hasattr(self, 'output_folder') or not os.path.exists(self.output_folder):
            QMessageBox.warning(self, "Warning", "No output folder found!")
            return
        
        # Verify all chapters are translated
        total = len(self.chapter_statuses)
        completed = sum(1 for s in self.chapter_statuses.values() if s.xhtml_exists)
        
        if completed < total:
            QMessageBox.warning(
                self,
                "Incomplete Translation",
                f"Only {completed}/{total} chapters are translated.\n\n"
                f"Please translate all chapters before building the final EPUB."
            )
            return
        
        # Call the parent's build_final_epub method
        if self.parent_app:
            self.parent_app.build_final_epub()
        else:
            QMessageBox.warning(self, "Warning", "Cannot access main application!")

