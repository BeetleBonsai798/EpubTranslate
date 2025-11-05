"""EPUB rebuilding from translated XHTML files."""

import os
from ebooklib import epub


class EpubRebuilder:
    """Rebuilds EPUB with translated content."""

    def __init__(self, original_epub_path):
        """Load original EPUB."""
        self.original_book = epub.read_epub(original_epub_path)
        self.html_items = [
            item for item in self.original_book.get_items()
            if isinstance(item, epub.EpubHtml)
        ]
        self.new_book = None

    def update_with_translated_xhtml(self, xhtml_folder):
        """Update EPUB items with translated XHTML files."""
        translated_xhtml_map = {}

        # Load all translated XHTML files
        for i, item in enumerate(self.html_items, start=1):
            xhtml_path = os.path.join(xhtml_folder, f"{i}.xhtml")

            if os.path.exists(xhtml_path):
                with open(xhtml_path, 'r', encoding='utf-8') as f:
                    translated_xhtml = f.read()

                # Update item content
                item.set_content(translated_xhtml.encode('utf-8'))

                # Store for TOC translation
                translated_xhtml_map[item.file_name] = translated_xhtml

        return translated_xhtml_map

    def write_epub(self, output_path):
        """Write the final translated EPUB by creating a new book from scratch."""
        # Create new EPUB book
        self.new_book = epub.EpubBook()

        # Copy metadata from original but set language to English
        # Get existing metadata
        identifiers = self.original_book.get_metadata('DC', 'identifier')
        titles = self.original_book.get_metadata('DC', 'title')
        creators = self.original_book.get_metadata('DC', 'creator')
        descriptions = self.original_book.get_metadata('DC', 'description')
        dates = self.original_book.get_metadata('DC', 'date')
        sources = self.original_book.get_metadata('DC', 'source')

        # Set identifier, title, and language (required fields)
        if identifiers:
            self.new_book.set_identifier(identifiers[0][0])
        else:
            self.new_book.set_identifier('translated-book-id')

        if titles:
            self.new_book.set_title(titles[0][0])
        else:
            self.new_book.set_title('Translated Book')

        # Set language to English (this is the fix!)
        self.new_book.set_language('en')

        # Copy authors
        if creators:
            for creator in creators:
                self.new_book.add_author(creator[0])

        # Copy other metadata
        if descriptions:
            for desc in descriptions:
                self.new_book.add_metadata('DC', 'description', desc[0])

        if dates:
            for date in dates:
                self.new_book.add_metadata('DC', 'date', date[0])

        if sources:
            for source in sources:
                source_id = source[1].get('id', '') if len(source) > 1 and isinstance(source[1], dict) else ''
                if source_id:
                    self.new_book.add_metadata('DC', 'source', source[0], {'id': source_id})
                else:
                    self.new_book.add_metadata('DC', 'source', source[0])

        # Copy all items (HTML, images, CSS, etc.)
        for item in self.original_book.get_items():
            self.new_book.add_item(item)

        # Copy spine
        self.new_book.spine = self.original_book.spine

        # Copy TOC
        self.new_book.toc = self.original_book.toc

        # Write the new EPUB
        epub.write_epub(output_path, self.new_book)