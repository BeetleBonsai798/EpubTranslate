"""Main application window for the EPUB translator."""

import os
import sys
import queue
import threading
import time
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QCheckBox, QSpinBox, QVBoxLayout, QHBoxLayout,
                             QRadioButton, QTabWidget, QTextEdit, QScrollArea, QGroupBox,
                             QDoubleSpinBox, QComboBox, QListWidget, QListWidgetItem,
                             QAbstractItemView, QMessageBox, QMenuBar, QAction, QSplitter)
from PyQt5.QtGui import QFont
from ebooklib import epub

from ..config import ConfigManager
from ..api import OpenRouterFetcher
from ..core import TranslationWorker
from .chapter_overview_widget import ChapterOverviewWidget


class EpubTranslatorApp(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced EPUB Translator")
        self.setMinimumSize(800, 600)

        # Initialize config manager
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()

        # Set window geometry from config
        geometry = self.config.get('window_geometry', {})
        self.setGeometry(
            geometry.get('x', 100),
            geometry.get('y', 100),
            geometry.get('width', 1400),
            geometry.get('height', 1000)
        )

        self.workers = {}
        self.worker_count = 0
        self.chapters = []
        self.epub_book = None
        self.epub_path = None

        # OpenRouter data
        self.available_models = []
        self.current_providers = []
        self.current_provider_details = []
        self.fetcher_thread = None

        # File tracking
        self.current_character_file = ""
        self.current_place_file = ""
        self.current_terms_file = ""
        self.current_notes_file = ""

        self.init_ui()
        self.load_config_to_ui()

    def init_ui(self):
        """Initialize the UI."""
        # Create menu bar
        self.create_menu_bar()

        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Create main splitter (horizontal)
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)

        # Left panel for settings
        left_panel = QWidget()
        left_panel.setMinimumWidth(300)
        self.setup_settings_panel(left_panel)
        main_splitter.addWidget(left_panel)

        # Right panel with tabs
        self.setup_tabs_panel(main_splitter)

        # Set splitter proportions
        main_splitter.setSizes([350, 1050])
        main_splitter.setChildrenCollapsible(True)

    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        save_config_action = QAction('Save Configuration', self)
        save_config_action.triggered.connect(self.save_current_config)
        file_menu.addAction(save_config_action)

        load_config_action = QAction('Load Configuration', self)
        load_config_action.triggered.connect(self.load_config_from_file)
        file_menu.addAction(load_config_action)

        file_menu.addSeparator()

        save_session_action = QAction('Save Session', self)
        save_session_action.triggered.connect(self.save_current_session)
        file_menu.addAction(save_session_action)

        load_session_action = QAction('Load Last Session', self)
        load_session_action.triggered.connect(self.load_last_session)
        file_menu.addAction(load_session_action)

        file_menu.addSeparator()

        reset_config_action = QAction('Reset to Defaults', self)
        reset_config_action.triggered.connect(self.reset_to_defaults)
        file_menu.addAction(reset_config_action)

    def setup_settings_panel(self, panel):
        """Setup the left settings panel."""
        layout = QVBoxLayout()
        panel.setLayout(layout)

        # File selection
        self._add_file_selection(layout)

        # API Configuration
        self._add_api_configuration(layout)

        # Model Selection
        self._add_model_selection(layout)

        # Chapter Selection
        self._add_chapter_selection(layout)

        # Translation Settings
        self._add_translation_settings(layout)

        # Control buttons
        self._add_control_buttons(layout)

        # Add stretch to push everything to top
        layout.addStretch()

    def _add_file_selection(self, layout):
        """Add file selection section."""
        file_group = QGroupBox("EPUB File")
        file_layout = QVBoxLayout()

        epub_layout = QHBoxLayout()
        self.epub_path_entry = QLineEdit()
        self.epub_path_entry.setPlaceholderText("Select EPUB file...")
        epub_layout.addWidget(self.epub_path_entry)

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.select_epub_file)
        epub_layout.addWidget(browse_btn)

        file_layout.addLayout(epub_layout)

        # Total chapters label
        self.total_chapters_label = QLabel("No EPUB loaded")
        self.total_chapters_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.total_chapters_label.setWordWrap(True)
        file_layout.addWidget(self.total_chapters_label)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

    def _add_api_configuration(self, layout):
        """Add API configuration section."""
        api_group = QGroupBox("API Configuration")
        api_layout = QVBoxLayout()

        # OpenRouter/Custom toggle
        endpoint_toggle_layout = QHBoxLayout()
        self.openrouter_radio = QRadioButton("OpenRouter")
        self.custom_endpoint_radio = QRadioButton("Custom Endpoint")
        self.openrouter_radio.setChecked(True)
        self.openrouter_radio.toggled.connect(self.on_endpoint_type_changed)
        endpoint_toggle_layout.addWidget(self.openrouter_radio)
        endpoint_toggle_layout.addWidget(self.custom_endpoint_radio)
        endpoint_toggle_layout.addStretch()
        api_layout.addLayout(endpoint_toggle_layout)

        # OpenRouter API Key
        self.openrouter_container = QWidget()
        openrouter_layout = QVBoxLayout()
        openrouter_layout.setContentsMargins(0, 0, 0, 0)

        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("OpenRouter API Key:"))
        self.api_key_entry = QLineEdit()
        self.api_key_entry.setEchoMode(QLineEdit.Password)
        self.api_key_entry.setPlaceholderText("Enter your OpenRouter API key...")
        api_key_layout.addWidget(self.api_key_entry)

        self.show_api_key_btn = QPushButton("👁")
        self.show_api_key_btn.setMaximumWidth(30)
        self.show_api_key_btn.clicked.connect(self.toggle_api_key_visibility)
        api_key_layout.addWidget(self.show_api_key_btn)

        openrouter_layout.addLayout(api_key_layout)
        self.openrouter_container.setLayout(openrouter_layout)
        api_layout.addWidget(self.openrouter_container)

        # Custom Endpoint Configuration
        self.custom_endpoint_container = QWidget()
        custom_layout = QVBoxLayout()
        custom_layout.setContentsMargins(0, 0, 0, 0)

        # Endpoint URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Endpoint URL:"))
        self.custom_endpoint_url = QLineEdit()
        self.custom_endpoint_url.setPlaceholderText("https://api.example.com/v1")
        url_layout.addWidget(self.custom_endpoint_url)
        custom_layout.addLayout(url_layout)

        # Custom API Key
        custom_key_layout = QHBoxLayout()
        custom_key_layout.addWidget(QLabel("API Key:"))
        self.custom_endpoint_key = QLineEdit()
        self.custom_endpoint_key.setEchoMode(QLineEdit.Password)
        self.custom_endpoint_key.setPlaceholderText("Enter custom endpoint API key...")
        custom_key_layout.addWidget(self.custom_endpoint_key)

        self.show_custom_key_btn = QPushButton("👁")
        self.show_custom_key_btn.setMaximumWidth(30)
        self.show_custom_key_btn.clicked.connect(self.toggle_custom_key_visibility)
        custom_key_layout.addWidget(self.show_custom_key_btn)
        custom_layout.addLayout(custom_key_layout)

        # Model name for custom endpoint
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model Name:"))
        self.custom_endpoint_model = QLineEdit()
        self.custom_endpoint_model.setPlaceholderText("e.g., gpt-4, deepseek-chat")
        model_layout.addWidget(self.custom_endpoint_model)
        custom_layout.addLayout(model_layout)

        self.custom_endpoint_container.setLayout(custom_layout)
        self.custom_endpoint_container.setVisible(False)
        api_layout.addWidget(self.custom_endpoint_container)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

    def _add_model_selection(self, layout):
        """Add model selection section."""
        model_group = QGroupBox("Model & Providers")
        model_layout = QVBoxLayout()

        # Model selection container
        self.model_selection_container = QWidget()
        model_sel_layout = QVBoxLayout()
        model_sel_layout.setContentsMargins(0, 0, 0, 0)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        model_row.addWidget(self.model_combo)

        self.fetch_models_btn = QPushButton("Fetch")
        self.fetch_models_btn.setMaximumWidth(60)
        self.fetch_models_btn.clicked.connect(self.fetch_models)
        model_row.addWidget(self.fetch_models_btn)

        model_sel_layout.addLayout(model_row)

        # Provider selection
        provider_row = QHBoxLayout()
        self.available_providers_list = QListWidget()
        self.available_providers_list.setMaximumHeight(100)
        self.available_providers_list.setSelectionMode(QAbstractItemView.MultiSelection)

        provider_buttons = QVBoxLayout()
        self.add_provider_btn = QPushButton("Add →")
        self.add_provider_btn.setMaximumWidth(60)
        self.add_provider_btn.clicked.connect(self.add_provider)
        provider_buttons.addWidget(self.add_provider_btn)

        self.remove_provider_btn = QPushButton("← Remove")
        self.remove_provider_btn.setMaximumWidth(60)
        self.remove_provider_btn.clicked.connect(self.remove_provider)
        provider_buttons.addWidget(self.remove_provider_btn)

        self.selected_providers_list = QListWidget()
        self.selected_providers_list.setMaximumHeight(100)

        self.move_up_btn = QPushButton("↑")
        self.move_up_btn.setMaximumWidth(30)
        self.move_up_btn.clicked.connect(self.move_provider_up)
        provider_buttons.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("↓")
        self.move_down_btn.setMaximumWidth(30)
        self.move_down_btn.clicked.connect(self.move_provider_down)
        provider_buttons.addWidget(self.move_down_btn)

        self.selected_providers_list.itemSelectionChanged.connect(self.update_provider_buttons)
        self.update_provider_buttons()

        provider_row.addWidget(self.available_providers_list)
        provider_row.addLayout(provider_buttons)
        provider_row.addWidget(self.selected_providers_list)

        model_sel_layout.addLayout(provider_row)

        # Fetch providers button
        self.fetch_providers_btn = QPushButton("Fetch Providers for Selected Model")
        self.fetch_providers_btn.clicked.connect(self.fetch_providers)
        self.fetch_providers_btn.setEnabled(False)
        model_sel_layout.addWidget(self.fetch_providers_btn)

        self.model_selection_container.setLayout(model_sel_layout)
        model_layout.addWidget(self.model_selection_container)

        # API status
        self.api_status_label = QLabel("")
        self.api_status_label.setFont(QFont("Arial", 8))
        model_layout.addWidget(self.api_status_label)

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

    def _add_chapter_selection(self, layout):
        """Add chapter selection section."""
        chapter_group = QGroupBox("Chapter Selection")
        chapter_layout = QVBoxLayout()

        self.range_radio = QRadioButton("Chapter Range")
        self.range_radio.setChecked(True)
        self.csv_radio = QRadioButton("Comma-Separated")
        chapter_layout.addWidget(self.range_radio)
        chapter_layout.addWidget(self.csv_radio)

        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Start:"))
        self.start_chapter_entry = QLineEdit()
        self.start_chapter_entry.setMaximumWidth(60)
        range_layout.addWidget(self.start_chapter_entry)
        range_layout.addWidget(QLabel("End:"))
        self.end_chapter_entry = QLineEdit()
        self.end_chapter_entry.setMaximumWidth(60)
        range_layout.addWidget(self.end_chapter_entry)
        range_layout.addStretch()
        chapter_layout.addLayout(range_layout)

        csv_layout = QHBoxLayout()
        csv_layout.addWidget(QLabel("CSV:"))
        self.csv_entry = QLineEdit()
        self.csv_entry.setEnabled(False)
        self.csv_entry.setPlaceholderText("e.g., 1,3,5,7-10")
        csv_layout.addWidget(self.csv_entry)
        chapter_layout.addLayout(csv_layout)

        chapter_group.setLayout(chapter_layout)
        layout.addWidget(chapter_group)

        # Connect signals
        self.range_radio.toggled.connect(self.toggle_chapter_selection)
        self.csv_radio.toggled.connect(self.toggle_chapter_selection)

    def _add_translation_settings(self, layout):
        """Add translation settings section."""
        settings_group = QGroupBox("Translation Settings")
        settings_layout = QVBoxLayout()

        # Parameters row 1
        params_row1 = QHBoxLayout()
        params_row1.addWidget(QLabel("Chunk Tokens:"))
        self.max_tokens_entry = QLineEdit()
        self.max_tokens_entry.setMaximumWidth(80)
        params_row1.addWidget(self.max_tokens_entry)

        params_row1.addWidget(QLabel("Workers:"))
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 10)
        self.concurrency_spin.setMaximumWidth(60)
        params_row1.addWidget(self.concurrency_spin)
        params_row1.addStretch()

        settings_layout.addLayout(params_row1)

        # Parameters row 2
        params_row2 = QHBoxLayout()
        params_row2.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setMaximumWidth(80)
        params_row2.addWidget(self.temperature_spin)

        params_row2.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 16000)
        self.max_tokens_spin.setMaximumWidth(80)
        params_row2.addWidget(self.max_tokens_spin)
        params_row2.addStretch()

        settings_layout.addLayout(params_row2)

        # Parameters row 3
        params_row3 = QHBoxLayout()
        params_row3.addWidget(QLabel("Frequency Penalty:"))
        self.frequency_penalty_spin = QDoubleSpinBox()
        self.frequency_penalty_spin.setRange(-2.0, 2.0)
        self.frequency_penalty_spin.setSingleStep(0.01)
        self.frequency_penalty_spin.setDecimals(2)
        self.frequency_penalty_spin.setMaximumWidth(80)
        params_row3.addWidget(self.frequency_penalty_spin)
        params_row3.addWidget(QLabel("Top P:"))
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.01)
        self.top_p_spin.setDecimals(2)
        self.top_p_spin.setMaximumWidth(80)
        params_row3.addWidget(self.top_p_spin)
        params_row3.addStretch()

        settings_layout.addLayout(params_row3)

        # Parameters row 4 - Top K and Retries per provider
        params_row4 = QHBoxLayout()
        params_row4.addWidget(QLabel("Top K:"))
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(0, 100)
        self.top_k_spin.setMaximumWidth(80)
        self.top_k_spin.setToolTip("Top K sampling (0 = disabled, provider-dependent)")
        params_row4.addWidget(self.top_k_spin)

        params_row4.addWidget(QLabel("Retries per Provider:"))
        self.retries_per_provider_spin = QSpinBox()
        self.retries_per_provider_spin.setRange(1, 10)
        self.retries_per_provider_spin.setMaximumWidth(60)
        self.retries_per_provider_spin.setToolTip("Number of retry attempts for each provider before moving to the next")
        params_row4.addWidget(self.retries_per_provider_spin)
        params_row4.addStretch()

        settings_layout.addLayout(params_row4)

        # Parameters row 5 - Timeout
        params_row5 = QHBoxLayout()
        params_row5.addWidget(QLabel("Timeout (seconds):"))
        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 600.0)
        self.timeout_spin.setSingleStep(5.0)
        self.timeout_spin.setDecimals(1)
        self.timeout_spin.setMaximumWidth(80)
        self.timeout_spin.setToolTip("API request timeout in seconds")
        params_row5.addWidget(self.timeout_spin)
        params_row5.addStretch()

        settings_layout.addLayout(params_row5)

        # Context options
        self.context_mode_check = QCheckBox("Context Mode (Characters, Places, Terms)")
        self.notes_mode_check = QCheckBox("Translation Notes Mode")
        self.power_steering_check = QCheckBox("Power Steering (JSON instructions in user prompt)")
        self.send_previous_check = QCheckBox("Send Previous Chapters")
        self.send_previous_chunks_check = QCheckBox("Send Previous Chunks")

        settings_layout.addWidget(self.context_mode_check)
        settings_layout.addWidget(self.notes_mode_check)
        settings_layout.addWidget(self.power_steering_check)
        settings_layout.addWidget(self.send_previous_check)
        settings_layout.addWidget(self.send_previous_chunks_check)

        # Previous chapters count
        prev_layout = QHBoxLayout()
        prev_layout.addWidget(QLabel("Previous Chapters Count:"))
        self.previous_chapters_spin = QSpinBox()
        self.previous_chapters_spin.setRange(0, 10)
        self.previous_chapters_spin.setMaximumWidth(60)
        self.previous_chapters_spin.setEnabled(False)
        prev_layout.addWidget(self.previous_chapters_spin)
        prev_layout.addStretch()
        settings_layout.addLayout(prev_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Connect signals
        self.send_previous_check.toggled.connect(self.update_controls)
        self.context_mode_check.toggled.connect(self.update_controls)
        self.notes_mode_check.toggled.connect(self.update_controls)

    def _add_control_buttons(self, layout):
        """Add control buttons."""
        btn_layout = QVBoxLayout()
        self.translate_btn = QPushButton("🚀 Start Translation")
        self.translate_btn.setStyleSheet("QPushButton { font-weight: bold; padding: 8px; }")
        self.translate_btn.clicked.connect(self.start_translation)
        btn_layout.addWidget(self.translate_btn)

        self.stop_btn = QPushButton("⏹ Stop All")
        self.stop_btn.setStyleSheet("QPushButton { padding: 6px; }")
        self.stop_btn.clicked.connect(self.stop_translation)
        btn_layout.addWidget(self.stop_btn)

        layout.addLayout(btn_layout)

    def setup_tabs_panel(self, splitter):
        """Setup the right panel with tabs."""
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.on_tab_close_requested)
        splitter.addWidget(self.tabs)

        # Create chapter overview tab (always first)
        self.chapter_overview = ChapterOverviewWidget(self)
        self.tabs.addTab(self.chapter_overview, "📊 Chapter Overview")

        # Create display tabs
        self.character_tab = QTextEdit()
        self.character_tab.setReadOnly(True)
        self.character_tab.setFont(QFont("Consolas", 10))
        self.place_tab = QTextEdit()
        self.place_tab.setReadOnly(True)
        self.place_tab.setFont(QFont("Consolas", 10))
        self.terms_tab = QTextEdit()
        self.terms_tab.setReadOnly(True)
        self.terms_tab.setFont(QFont("Consolas", 10))
        self.notes_tab = QTextEdit()
        self.notes_tab.setReadOnly(True)
        self.notes_tab.setFont(QFont("Consolas", 10))

        # Add raw JSON display tab
        self.raw_json_tab = QTextEdit()
        self.raw_json_tab.setReadOnly(True)
        self.raw_json_tab.setFont(QFont("Courier New", 9))

        self.tabs.addTab(self.character_tab, "👤 Characters")
        self.tabs.addTab(self.place_tab, "🌍 Places")
        self.tabs.addTab(self.terms_tab, "⚡ Terms")
        self.tabs.addTab(self.notes_tab, "📝 Notes")
        self.tabs.addTab(self.raw_json_tab, "🔧 Raw JSON")

    # ==================== Configuration Methods ====================

    def load_config_to_ui(self):
        """Load configuration values to UI components."""
        # Endpoint type
        use_custom = self.config.get('use_custom_endpoint', False)
        if use_custom:
            self.custom_endpoint_radio.setChecked(True)
        else:
            self.openrouter_radio.setChecked(True)

        # API Keys and endpoints
        self.api_key_entry.setText(self.config.get('api_key', ''))
        self.custom_endpoint_url.setText(self.config.get('custom_endpoint_url', ''))
        self.custom_endpoint_key.setText(self.config.get('custom_endpoint_key', ''))
        self.custom_endpoint_model.setText(self.config.get('custom_endpoint_model', ''))

        # Model
        self.model_combo.setCurrentText(self.config.get('model', ''))

        # Chunk tokens
        self.max_tokens_entry.setText(str(self.config.get('chunk_tokens', 7000)))

        # Model parameters
        self.temperature_spin.setValue(self.config.get('temperature', 0.55))
        self.max_tokens_spin.setValue(self.config.get('max_tokens', 8000))
        self.frequency_penalty_spin.setValue(self.config.get('frequency_penalty', 0.0))
        self.top_p_spin.setValue(self.config.get('top_p', 1.0))
        self.top_k_spin.setValue(self.config.get('top_k', 0))
        self.timeout_spin.setValue(self.config.get('timeout', 60.0))
        self.retries_per_provider_spin.setValue(self.config.get('retries_per_provider', 1))

        # Selected providers
        self.selected_providers_list.clear()
        for provider in self.config.get('selected_providers', []):
            self.selected_providers_list.addItem(provider)

        # Context options
        self.context_mode_check.setChecked(self.config.get('context_mode', False))
        self.notes_mode_check.setChecked(self.config.get('notes_mode', False))
        self.power_steering_check.setChecked(self.config.get('power_steering', False))
        self.send_previous_check.setChecked(self.config.get('send_previous', False))
        self.previous_chapters_spin.setValue(self.config.get('previous_chapters', 1))
        self.send_previous_chunks_check.setChecked(self.config.get('send_previous_chunks', True))

        # Concurrency
        self.concurrency_spin.setValue(self.config.get('concurrent_workers', 3))

        # Chapter selection
        if self.config.get('chapter_selection_mode', 'range') == 'csv':
            self.csv_radio.setChecked(True)
        else:
            self.range_radio.setChecked(True)

        self.start_chapter_entry.setText(self.config.get('start_chapter', '1'))
        self.end_chapter_entry.setText(self.config.get('end_chapter', '1'))
        self.csv_entry.setText(self.config.get('csv_chapters', ''))

        # Last EPUB path
        self.epub_path_entry.setText(self.config.get('last_epub_path', ''))
        if self.epub_path_entry.text():
            self.load_epub_file(self.epub_path_entry.text())

        self.update_controls()

    def get_config_from_ui(self):
        """Extract configuration from current UI state."""
        config = {}

        # Endpoint configuration
        config['use_custom_endpoint'] = self.custom_endpoint_radio.isChecked()
        config['api_key'] = self.api_key_entry.text()
        config['custom_endpoint_url'] = self.custom_endpoint_url.text()
        config['custom_endpoint_key'] = self.custom_endpoint_key.text()
        config['custom_endpoint_model'] = self.custom_endpoint_model.text()

        # Model
        config['model'] = self.model_combo.currentText()

        # Chunk tokens
        try:
            config['chunk_tokens'] = int(self.max_tokens_entry.text())
        except ValueError:
            config['chunk_tokens'] = 7000

        # Model parameters
        config['temperature'] = self.temperature_spin.value()
        config['max_tokens'] = self.max_tokens_spin.value()
        config['frequency_penalty'] = self.frequency_penalty_spin.value()
        config['top_p'] = self.top_p_spin.value()
        config['top_k'] = self.top_k_spin.value()
        config['timeout'] = self.timeout_spin.value()
        config['retries_per_provider'] = self.retries_per_provider_spin.value()

        # Selected providers
        config['selected_providers'] = self.get_selected_providers()

        # Context options
        config['context_mode'] = self.context_mode_check.isChecked()
        config['notes_mode'] = self.notes_mode_check.isChecked()
        config['power_steering'] = self.power_steering_check.isChecked()
        config['send_previous'] = self.send_previous_check.isChecked()
        config['previous_chapters'] = self.previous_chapters_spin.value()
        config['send_previous_chunks'] = self.send_previous_chunks_check.isChecked()

        # Concurrency
        config['concurrent_workers'] = self.concurrency_spin.value()

        # Chapter selection
        config['chapter_selection_mode'] = 'csv' if self.csv_radio.isChecked() else 'range'
        config['start_chapter'] = self.start_chapter_entry.text()
        config['end_chapter'] = self.end_chapter_entry.text()
        config['csv_chapters'] = self.csv_entry.text()

        # Last EPUB path
        config['last_epub_path'] = self.epub_path_entry.text()

        # Window geometry
        config['window_geometry'] = {
            'x': self.x(),
            'y': self.y(),
            'width': self.width(),
            'height': self.height()
        }

        return config

    def save_current_config(self):
        """Save current UI state to configuration."""
        self.config = self.get_config_from_ui()

        if self.config_manager.save_config(self.config):
            QMessageBox.information(self, "Success", "Configuration saved successfully!")
        else:
            QMessageBox.critical(self, "Error", "Failed to save configuration!")

    def load_config_from_file(self):
        """Load configuration from file."""
        config_path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", "", "JSON Files (*.json)"
        )

        if config_path:
            try:
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # Merge with current config
                self.config.update(loaded_config)
                self.load_config_to_ui()

                QMessageBox.information(self, "Success", "Configuration loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load configuration: {str(e)}")

    def save_current_session(self):
        """Save current session for continuation."""
        if not self.chapters:
            QMessageBox.warning(self, "Warning", "No EPUB file loaded!")
            return

        epub_path = self.epub_path_entry.text()
        if not epub_path:
            QMessageBox.warning(self, "Warning", "No EPUB file selected!")
            return

        epub_name = os.path.splitext(os.path.basename(epub_path))[0]
        output_folder = os.path.join(os.path.dirname(__file__), "..", "..", "..", f"{epub_name}_translated")

        # Find completed chapters
        completed_chapters = []
        if os.path.exists(output_folder):
            for i in range(1, len(self.chapters) + 1):
                if os.path.exists(os.path.join(output_folder, "xhtml", f"{i}.xhtml")):
                    completed_chapters.append(i)

        session_data = {
            'epub_path': epub_path,
            'epub_name': epub_name,
            'total_chapters': len(self.chapters),
            'completed_chapters': completed_chapters,
            'output_folder': output_folder,
            'last_completed': max(completed_chapters) if completed_chapters else 0,
            'config': self.get_config_from_ui(),
            'timestamp': str(time.time())
        }

        if self.config_manager.save_last_session(session_data):
            QMessageBox.information(
                self, "Success",
                f"Session saved! Completed chapters: {len(completed_chapters)}/{len(self.chapters)}"
            )
        else:
            QMessageBox.critical(self, "Error", "Failed to save session!")

    def load_last_session(self):
        """Load last session for continuation."""
        session_data = self.config_manager.load_last_session()

        if not session_data:
            QMessageBox.information(self, "Info", "No previous session found!")
            return

        # Ask user if they want to continue
        completed = len(session_data.get('completed_chapters', []))
        total = session_data.get('total_chapters', 0)

        reply = QMessageBox.question(
            self, "Continue Translation",
            f"Found previous session:\n"
            f"EPUB: {session_data.get('epub_name', 'Unknown')}\n"
            f"Progress: {completed}/{total} chapters completed\n"
            f"Last chapter: {session_data.get('last_completed', 0)}\n\n"
            f"Do you want to continue this translation?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Load the session
            epub_path = session_data.get('epub_path', '')
            if epub_path and os.path.exists(epub_path):
                self.epub_path_entry.setText(epub_path)
                self.load_epub_file(epub_path)

                # Load configuration from session
                if 'config' in session_data:
                    self.config.update(session_data['config'])
                    self.load_config_to_ui()

                # Set up for continuation
                last_completed = session_data.get('last_completed', 0)
                self.start_chapter_entry.setText(str(last_completed + 1))
                self.end_chapter_entry.setText(str(total))

                QMessageBox.information(
                    self, "Session Loaded",
                    f"Session loaded successfully!\n"
                    f"Ready to continue from chapter {last_completed + 1}"
                )
            else:
                QMessageBox.critical(self, "Error", "EPUB file from session not found!")

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        reply = QMessageBox.question(
            self, "Reset Configuration",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.config = self.config_manager.default_config.copy()
            self.load_config_to_ui()
            QMessageBox.information(self, "Success", "Configuration reset to defaults!")

    def closeEvent(self, event):
        """Save configuration on close."""
        self.config = self.get_config_from_ui()
        self.config_manager.save_config(self.config)
        event.accept()

    # ==================== UI Interaction Methods ====================

    def on_endpoint_type_changed(self):
        """Handle switching between OpenRouter and custom endpoint."""
        is_openrouter = self.openrouter_radio.isChecked()

        self.openrouter_container.setVisible(is_openrouter)
        self.custom_endpoint_container.setVisible(not is_openrouter)
        self.model_selection_container.setVisible(is_openrouter)

        if not is_openrouter:
            self.api_status_label.setText("Using custom endpoint - providers not available")
        else:
            self.api_status_label.setText("")

    def toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.api_key_entry.echoMode() == QLineEdit.Password:
            self.api_key_entry.setEchoMode(QLineEdit.Normal)
            self.show_api_key_btn.setText("🙈")
        else:
            self.api_key_entry.setEchoMode(QLineEdit.Password)
            self.show_api_key_btn.setText("👁")

    def toggle_custom_key_visibility(self):
        """Toggle custom endpoint key visibility."""
        if self.custom_endpoint_key.echoMode() == QLineEdit.Password:
            self.custom_endpoint_key.setEchoMode(QLineEdit.Normal)
            self.show_custom_key_btn.setText("🙈")
        else:
            self.custom_endpoint_key.setEchoMode(QLineEdit.Password)
            self.show_custom_key_btn.setText("👁")

    def toggle_chapter_selection(self):
        """Toggle between range and CSV chapter selection."""
        self.start_chapter_entry.setEnabled(self.range_radio.isChecked())
        self.end_chapter_entry.setEnabled(self.range_radio.isChecked())
        self.csv_entry.setEnabled(self.csv_radio.isChecked())

    def update_controls(self):
        """Update control states based on settings."""
        # Enable/disable previous chapters spinner
        previous_enabled = self.send_previous_check.isChecked()
        self.previous_chapters_spin.setEnabled(previous_enabled)

        # Force single worker if any context mode is enabled
        force_single_worker = self.context_mode_check.isChecked() or self.notes_mode_check.isChecked()
        if force_single_worker:
            self.concurrency_spin.setValue(1)
            self.concurrency_spin.setEnabled(False)
        else:
            self.concurrency_spin.setEnabled(True)
            if self.concurrency_spin.value() == 1:
                self.concurrency_spin.setValue(3)

    def on_tab_close_requested(self, index):
        """Handle tab close request."""
        # Don't allow closing the first tab (Chapter Overview)
        if index == 0:
            return
        widget = self.tabs.widget(index)
        if widget:
            widget.deleteLater()
        self.tabs.removeTab(index)

    # ==================== Provider/Model Methods ====================

    def on_model_changed(self, model_text):
        """Enable fetch providers button when model is selected."""
        self.fetch_providers_btn.setEnabled(bool(model_text.strip()) and self.openrouter_radio.isChecked())

    def fetch_models(self):
        """Fetch available models from OpenRouter."""
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            return

        self.fetch_models_btn.setEnabled(False)
        self.api_status_label.setText("Fetching models...")

        self.fetcher_thread = OpenRouterFetcher("models")
        self.fetcher_thread.models_fetched.connect(self.on_models_fetched)
        self.fetcher_thread.error_occurred.connect(self.on_api_error)
        self.fetcher_thread.progress_updated.connect(self.on_api_progress)
        self.fetcher_thread.finished.connect(self.on_api_finished)
        self.fetcher_thread.start()

    def fetch_providers(self):
        """Fetch providers for the selected model."""
        model_text = self.model_combo.currentText().strip()
        if not model_text:
            QMessageBox.warning(self, "Warning", "Please select a model first")
            return

        # Clean the model ID
        model_id = model_text.split(' ')[0].split('(')[0].strip()

        if self.fetcher_thread and self.fetcher_thread.isRunning():
            return

        self.fetch_providers_btn.setEnabled(False)
        self.api_status_label.setText("Fetching providers...")

        self.fetcher_thread = OpenRouterFetcher("providers", model_id)
        self.fetcher_thread.providers_fetched.connect(self.on_providers_fetched)
        self.fetcher_thread.provider_details_fetched.connect(self.on_provider_details_fetched)
        self.fetcher_thread.error_occurred.connect(self.on_api_error)
        self.fetcher_thread.progress_updated.connect(self.on_api_progress)
        self.fetcher_thread.finished.connect(self.on_api_finished)
        self.fetcher_thread.start()

    def on_models_fetched(self, models):
        """Handle fetched models."""
        self.available_models = models
        self.model_combo.clear()

        # Sort models by name
        sorted_models = sorted(models, key=lambda x: x['name'].lower())

        for model in sorted_models:
            model_display = model['id']
            self.model_combo.addItem(model_display, model['id'])

        # Try to restore previous selection
        current_text = self.config.get('model', 'deepseek/deepseek-chat-v3-0324')
        index = self.model_combo.findData(current_text)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        else:
            self.model_combo.setCurrentText(current_text)

    def on_providers_fetched(self, model_id, providers):
        """Handle fetched providers."""
        self.current_providers = providers

    def on_provider_details_fetched(self, model_id, provider_details):
        """Handle fetched provider details."""
        self.current_provider_details = provider_details
        self.available_providers_list.clear()

        for detail in provider_details:
            display_text = (f"{detail['provider_id']} | "
                            f"{detail['pricing']} | "
                            f"ctx:{detail['context_length']} | "
                            f"{detail['quantization']} | "
                            f"uptime:{detail['uptime']}")

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, detail['provider_id'])

            tooltip = (f"Provider: {detail['provider_name']}\n"
                       f"ID: {detail['provider_id']}\n"
                       f"Pricing: {detail['pricing']}\n"
                       f"Context Length: {detail['context_length']}\n"
                       f"Quantization: {detail['quantization']}\n"
                       f"Uptime (30m): {detail['uptime']}")
            item.setToolTip(tooltip)

            self.available_providers_list.addItem(item)

        self.api_status_label.setText(f"Found {len(provider_details)} providers for {model_id}")

    def on_api_error(self, error_msg):
        """Handle API errors."""
        QMessageBox.critical(self, "API Error", error_msg)
        self.api_status_label.setText(f"Error: {error_msg}")

    def on_api_progress(self, message):
        """Handle progress updates."""
        self.api_status_label.setText(message)

    def on_api_finished(self):
        """Handle API operation completion."""
        self.fetch_models_btn.setEnabled(True)
        self.fetch_providers_btn.setEnabled(
            bool(self.model_combo.currentText().strip()) and self.openrouter_radio.isChecked())

    def add_provider(self):
        """Add selected providers to the selected list."""
        for item in self.available_providers_list.selectedItems():
            provider_id = item.data(Qt.UserRole)
            if not provider_id:
                provider_id = item.text().split(' | ')[0]

            # Check if already in selected list
            found = False
            for i in range(self.selected_providers_list.count()):
                if self.selected_providers_list.item(i).text() == provider_id:
                    found = True
                    break

            if not found:
                self.selected_providers_list.addItem(provider_id)

    def remove_provider(self):
        """Remove selected providers from the selected list."""
        for item in self.selected_providers_list.selectedItems():
            row = self.selected_providers_list.row(item)
            self.selected_providers_list.takeItem(row)

    def move_provider_up(self):
        """Move selected provider up in the list."""
        selected_items = self.selected_providers_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            row = self.selected_providers_list.row(item)
            if row > 0:
                self.selected_providers_list.takeItem(row)
                self.selected_providers_list.insertItem(row - 1, item)
                item.setSelected(True)

    def move_provider_down(self):
        """Move selected provider down in the list."""
        selected_items = self.selected_providers_list.selectedItems()
        if not selected_items:
            return

        for item in reversed(selected_items):
            row = self.selected_providers_list.row(item)
            if row < self.selected_providers_list.count() - 1:
                self.selected_providers_list.takeItem(row)
                self.selected_providers_list.insertItem(row + 1, item)
                item.setSelected(True)

    def update_provider_buttons(self):
        """Enable/disable provider movement buttons based on selection."""
        selected_items = self.selected_providers_list.selectedItems()
        if not selected_items:
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            return

        can_move_up = any(self.selected_providers_list.row(item) > 0 for item in selected_items)
        self.move_up_btn.setEnabled(can_move_up)

        can_move_down = any(
            self.selected_providers_list.row(item) < self.selected_providers_list.count() - 1
            for item in selected_items
        )
        self.move_down_btn.setEnabled(can_move_down)

    def get_selected_providers(self):
        """Get list of selected providers in order."""
        providers = []
        for i in range(self.selected_providers_list.count()):
            providers.append(self.selected_providers_list.item(i).text())
        return providers

    # ==================== File/EPUB Methods ====================

    def select_epub_file(self):
        """Select EPUB file."""
        epub_path, _ = QFileDialog.getOpenFileName(self, "Select EPUB File", "", "EPUB Files (*.epub)")
        if epub_path:
            self.epub_path_entry.setText(epub_path)
            self.load_epub_file(epub_path)

    def load_epub_file(self, epub_path):
        """Load EPUB file and extract chapters."""
        if not os.path.exists(epub_path):
            return

        try:
            self.epub_path = epub_path  # Store for rebuilding
            self.epub_book = epub.read_epub(epub_path)
            self.chapters = [item.content.decode('utf-8')
                             for item in self.epub_book.get_items() if isinstance(item, epub.EpubHtml)]

            epub_name = os.path.splitext(os.path.basename(epub_path))[0]

            # Truncate long names for display
            display_name = epub_name
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."

            self.total_chapters_label.setText(f"📚 {display_name} | Chapters: {len(self.chapters)}")
            self.total_chapters_label.setToolTip(f"Full name: {epub_name}\nChapters: {len(self.chapters)}")

            output_folder = os.path.join(os.path.dirname(__file__), "..", "..", "..", f"{epub_name}_translated")

            # Update file paths
            context_folder = os.path.join(output_folder, "context")
            self.current_character_file = os.path.join(context_folder, f"{epub_name}_characters.json")
            self.current_place_file = os.path.join(context_folder, f"{epub_name}_places.json")
            self.current_terms_file = os.path.join(context_folder, f"{epub_name}_terms.json")
            self.current_notes_file = os.path.join(context_folder, f"{epub_name}_notes.json")

            # Update chapter overview
            self.chapter_overview.update_epub_info(epub_path, self.chapters, epub_name)

            # Load and display existing files
            self.update_all_displays()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load EPUB file: {str(e)}")

    # ==================== Translation Methods ====================

    def start_translation(self):
        """Start the translation process."""
        if not self.chapters:
            QMessageBox.warning(self, "Warning", "No EPUB file loaded!")
            return

        if not self.epub_book:
            QMessageBox.warning(self, "Warning", "EPUB book object not available!")
            return

        # Check API key based on endpoint type
        if self.custom_endpoint_radio.isChecked():
            api_key = self.custom_endpoint_key.text().strip()
            if not api_key:
                QMessageBox.warning(self, "Warning", "Please enter your custom endpoint API key!")
                return

            custom_url = self.custom_endpoint_url.text().strip()
            if not custom_url:
                QMessageBox.warning(self, "Warning", "Please enter your custom endpoint URL!")
                return

            model_id = self.custom_endpoint_model.text().strip()
            if not model_id:
                QMessageBox.warning(self, "Warning", "Please enter a model name!")
                return

            selected_providers = []
            endpoint_config = {
                'use_custom': True,
                'base_url': custom_url,
                'api_key': api_key
            }
        else:
            api_key = self.api_key_entry.text().strip()
            if not api_key:
                QMessageBox.warning(self, "Warning", "Please enter your OpenRouter API key!")
                return

            model_id = self.model_combo.currentText().strip()
            selected_providers = self.get_selected_providers()
            if not selected_providers:
                QMessageBox.warning(self, "Warning", "No providers selected. Using default providers.")
                selected_providers = self.config['selected_providers']

            endpoint_config = {
                'use_custom': False,
                'base_url': "https://openrouter.ai/api/v1",
                'api_key': api_key
            }

        # Get selected chapters
        if self.range_radio.isChecked():
            try:
                start = int(self.start_chapter_entry.text())
                end = int(self.end_chapter_entry.text())
                selected_chapters = self.chapters[start - 1:end]
                chapter_numbers = list(range(start, end + 1))
            except ValueError:
                QMessageBox.warning(self, "Error", "Invalid chapter range!")
                return
        else:
            try:
                chapter_numbers = []
                parts = self.csv_entry.text().split(',')
                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        start_range, end_range = map(int, part.split('-'))
                        chapter_numbers.extend(range(start_range, end_range + 1))
                    else:
                        chapter_numbers.append(int(part))
                selected_chapters = [self.chapters[i - 1] for i in chapter_numbers]
            except (ValueError, IndexError):
                QMessageBox.warning(self, "Error", "Invalid chapter numbers!")
                return

        # Set up chapter queue
        chapter_queue = queue.Queue()
        for chap_num, chapter in zip(chapter_numbers, selected_chapters):
            chapter_queue.put((chap_num, chapter))

        # Set up output folder
        epub_path = self.epub_path_entry.text()
        epub_name = os.path.splitext(os.path.basename(epub_path))[0]
        output_folder = os.path.join(os.path.dirname(__file__), "..", "..", "..", f"{epub_name}_translated")
        os.makedirs(output_folder, exist_ok=True)

        # Update file paths
        context_folder = os.path.join(output_folder, "context")
        self.current_character_file = os.path.join(context_folder, f"{epub_name}_characters.json")
        self.current_place_file = os.path.join(context_folder, f"{epub_name}_places.json")
        self.current_terms_file = os.path.join(context_folder, f"{epub_name}_terms.json")
        self.current_notes_file = os.path.join(context_folder, f"{epub_name}_notes.json")

        # Load existing files
        self.update_all_displays()

        # Get chunk tokens
        try:
            chunk_tokens = int(self.max_tokens_entry.text())
        except ValueError:
            chunk_tokens = 7000

        # Determine number of workers
        num_workers = self.concurrency_spin.value()

        # Create and start workers
        for _ in range(num_workers):
            worker_id = self.worker_count
            self.worker_count += 1

            log_widget = self.create_tab(worker_id)

            worker = TranslationWorker(
                output_folder=output_folder,
                model=model_id,
                max_tokens_per_chunk=chunk_tokens,
                send_previous=self.send_previous_check.isChecked(),
                previous_chapters=self.previous_chapters_spin.value(),
                send_previous_chunks=self.send_previous_chunks_check.isChecked(),
                worker_id=worker_id,
                context_mode=self.context_mode_check.isChecked(),
                notes_mode=self.notes_mode_check.isChecked(),
                power_steering=self.power_steering_check.isChecked(),
                epub_name=epub_name,
                chapter_queue=chapter_queue,
                all_chapters=self.chapters,
                temperature=self.temperature_spin.value(),
                max_tokens=self.max_tokens_spin.value(),
                frequency_penalty=self.frequency_penalty_spin.value(),
                top_p=self.top_p_spin.value(),
                top_k=self.top_k_spin.value(),
                timeout=self.timeout_spin.value(),
                providers_list=selected_providers,
                api_key=endpoint_config['api_key'],
                epub_book=self.epub_book,
                endpoint_config=endpoint_config,
                retries_per_provider=self.retries_per_provider_spin.value()
            )

            thread = threading.Thread(target=worker.run)

            # Connect signals
            worker.update_progress.connect(
                lambda text, wid, color, log=log_widget: self.update_progress(text, wid, color, log)
            )
            worker.status_updated.connect(self.update_worker_status)
            worker.finished.connect(self.cleanup_worker)
            worker.characters_updated.connect(self.update_character_display)
            worker.places_updated.connect(self.update_place_display)
            worker.terms_updated.connect(self.update_terms_display)
            worker.notes_updated.connect(self.update_notes_display)
            worker.raw_json_updated.connect(self.update_raw_json_display)
            worker.chapter_completed.connect(self.on_chapter_completed)

            self.workers[worker_id] = {
                'thread': thread,
                'worker': worker,
                'log': log_widget,
                'tab_index': self.tabs.count() - 1
            }

            self.tabs.setTabText(self.workers[worker_id]['tab_index'], f"Worker {worker_id + 1} ▶")
            thread.start()

    def stop_translation(self):
        """Stop all translation workers."""
        for worker_id, w in self.workers.items():
            w['worker'].stop()
            w['thread'].join()
        self.workers.clear()

    def create_tab(self, worker_id):
        """Create a tab for a worker."""
        scroll = QScrollArea()
        content = QWidget()
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 9))

        layout = QVBoxLayout()
        layout.addWidget(text_edit)
        content.setLayout(layout)

        scroll.setWidget(content)
        scroll.setWidgetResizable(True)

        self.tabs.addTab(scroll, f"Worker {worker_id + 1}")
        return text_edit

    def update_progress(self, text, worker_id, color, log_widget):
        """Update progress text in worker tab."""
        cursor = log_widget.textCursor()
        cursor.movePosition(cursor.End)

        format_table = {
            "red": Qt.red,
            "green": Qt.darkGreen,
            "blue": Qt.blue,
            "black": Qt.black,
            "orange": Qt.darkYellow
        }

        log_widget.setTextColor(format_table[color])
        cursor.insertText(text)
        log_widget.ensureCursorVisible()

    def update_worker_status(self, worker_id, chapter_number, current_chunk, total_chunks):
        """Update worker status in tab."""
        if worker_id in self.workers:
            status_text = f"Worker {worker_id + 1}: Ch.{chapter_number} Part {current_chunk}/{total_chunks}"
            tab_index = self.workers[worker_id]['tab_index']
            self.tabs.setTabText(tab_index, status_text)

    def cleanup_worker(self, worker_id):
        """Clean up worker after completion."""
        if worker_id in self.workers:
            tab_index = self.workers[worker_id]['tab_index']
            self.tabs.setTabText(tab_index, f"Worker {worker_id + 1} ✓")
            del self.workers[worker_id]
            
            # Refresh chapter overview when workers finish
            if len(self.workers) == 0:
                self.chapter_overview.refresh_status()

    def on_chapter_completed(self, chapter_number):
        """Handle chapter completion."""
        self.chapter_overview.refresh_status()

    def build_final_epub(self):
        """Build final EPUB with TOC translation - called manually from Build EPUB button."""
        if not self.epub_path:
            return

        try:
            from ..core.epub_rebuilder import EpubRebuilder
            from ..core.toc_translation_worker import TocTranslationWorker
            from ..core.context_manager import ContextManager

            epub_name = os.path.splitext(os.path.basename(self.epub_path))[0]
            output_folder = os.path.join(os.path.dirname(__file__), "..", "..", "..", f"{epub_name}_translated")
            xhtml_folder = os.path.join(output_folder, "xhtml")

            # Check if xhtml folder exists and has files
            if not os.path.exists(xhtml_folder) or not os.listdir(xhtml_folder):
                print("No translated XHTML files found, skipping EPUB rebuild")
                return

            print(f"🔨 Rebuilding EPUB from translated XHTML files...")

            # Create rebuilder
            rebuilder = EpubRebuilder(self.epub_path)

            # Update with translated XHTML
            translated_map = rebuilder.update_with_translated_xhtml(xhtml_folder)

            print(f"✓ Updated {len(translated_map)} chapters in EPUB")

            # Create TOC translation tab
            toc_log_widget = self.create_tab_for_toc()

            # Get endpoint config
            if self.custom_endpoint_radio.isChecked():
                api_key = self.custom_endpoint_key.text().strip()
                base_url = self.custom_endpoint_url.text().strip()
                model = self.custom_endpoint_model.text().strip()
            else:
                api_key = self.api_key_entry.text().strip()
                base_url = "https://openrouter.ai/api/v1"
                model = self.model_combo.currentText().strip()

            endpoint_config = {
                'api_key': api_key,
                'base_url': base_url,
                'model': model
            }

            # Get selected providers
            selected_providers = []
            for i in range(self.selected_providers_list.count()):
                selected_providers.append(self.selected_providers_list.item(i).text())

            if not selected_providers:
                selected_providers = ['deepseek/deepseek-v3.2-exp']

            # Create context manager to load existing context
            context_manager = ContextManager(
                output_folder,
                epub_name,
                context_mode=self.context_mode_check.isChecked(),
                notes_mode=self.notes_mode_check.isChecked()
            )

            # Create TOC translation worker with full settings
            self.toc_worker = TocTranslationWorker(
                original_book=rebuilder.original_book,
                translated_xhtml_map=translated_map,
                context_manager=context_manager,
                endpoint_config=endpoint_config,
                batch_size=30,
                providers_list=selected_providers,
                temperature=self.temperature_spin.value(),
                max_tokens=self.max_tokens_spin.value(),
                frequency_penalty=self.frequency_penalty_spin.value(),
                top_p=self.top_p_spin.value(),
                top_k=self.top_k_spin.value(),
                timeout=self.timeout_spin.value(),
                retries_per_provider=self.retries_per_provider_spin.value()
            )

            # Create thread
            toc_thread = threading.Thread(target=self.toc_worker.run)

            # Connect signals
            self.toc_worker.update_progress.connect(
                lambda text, color, log=toc_log_widget: self.update_toc_progress(text, color, log)
            )
            self.toc_worker.raw_json_updated.connect(self.update_raw_json_display)
            self.toc_worker.toc_item_translated.connect(self.update_toc_item_status)
            self.toc_worker.finished.connect(
                lambda success, msg: self.on_toc_translation_finished(success, msg, rebuilder, output_folder, epub_name)
            )

            # Store worker reference
            self.toc_thread = toc_thread
            self.toc_log_widget = toc_log_widget

            # Start TOC translation
            print("🔄 Starting TOC Translation in separate thread...")
            toc_thread.start()

        except Exception as e:
            print(f"❌ Error rebuilding EPUB: {str(e)}")
            import traceback
            traceback.print_exc()

            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "EPUB Rebuild Error",
                f"Translation completed but EPUB rebuild failed:\n{str(e)}\n\nTranslated XHTML files are available in the output folder."
            )

    def create_tab_for_toc(self):
        """Create a tab for TOC translation."""
        scroll = QScrollArea()
        content = QWidget()
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 9))

        layout = QVBoxLayout()
        layout.addWidget(text_edit)
        content.setLayout(layout)

        scroll.setWidget(content)
        scroll.setWidgetResizable(True)

        self.tabs.addTab(scroll, "📚 TOC Translation")
        return text_edit

    def update_toc_progress(self, text, color, log_widget):
        """Update TOC progress text in tab."""
        cursor = log_widget.textCursor()
        cursor.movePosition(cursor.End)

        format_table = {
            "red": Qt.red,
            "green": Qt.darkGreen,
            "blue": Qt.blue,
            "black": Qt.black,
            "orange": Qt.darkYellow,
            "yellow": Qt.darkYellow,
            "cyan": Qt.cyan,
            "white": Qt.black
        }

        log_widget.setTextColor(format_table.get(color, Qt.black))
        cursor.insertText(text)
        log_widget.ensureCursorVisible()

    def update_toc_item_status(self, current, total, original, translated):
        """Update the TOC translation tab title with progress."""
        progress_pct = int((current / total) * 100) if total > 0 else 0
        # Find the TOC tab and update its title
        for i in range(self.tabs.count()):
            if "TOC Translation" in self.tabs.tabText(i):
                self.tabs.setTabText(i, f"📚 TOC Translation ({current}/{total} - {progress_pct}%)")
                break

    def on_toc_translation_finished(self, success, message, rebuilder, output_folder, epub_name):
        """Handle TOC translation completion."""
        from PyQt5.QtWidgets import QMessageBox

        # Update tab title
        for i in range(self.tabs.count()):
            if "TOC Translation" in self.tabs.tabText(i):
                if success:
                    self.tabs.setTabText(i, "📚 TOC Translation ✓")
                else:
                    self.tabs.setTabText(i, "📚 TOC Translation ❌")
                break

        if success:
            try:
                # Write final EPUB
                output_epub = os.path.join(output_folder, f"{epub_name}_translated.epub")
                rebuilder.write_epub(output_epub)

                print(f"✅ Translated EPUB created: {output_epub}")

                QMessageBox.information(
                    self,
                    "EPUB Build Complete",
                    f"EPUB built successfully!\n\nTranslated EPUB saved to:\n{output_epub}"
                )
            except Exception as e:
                print(f"❌ Error writing EPUB: {str(e)}")
                import traceback
                traceback.print_exc()

                QMessageBox.warning(
                    self,
                    "EPUB Write Error",
                    f"TOC translation succeeded but EPUB write failed:\n{str(e)}"
                )
        else:
            QMessageBox.warning(
                self,
                "TOC Translation Failed",
                f"TOC translation failed: {message}\n\nTranslated XHTML files are available in the output folder."
            )

    # ==================== Display Update Methods ====================

    def update_all_displays(self):
        """Update all display tabs."""
        self.update_character_display()
        self.update_place_display()
        self.update_terms_display()
        self.update_notes_display()

    def update_character_display(self):
        """Update character display tab."""
        if os.path.exists(self.current_character_file):
            try:
                import json
                with open(self.current_character_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                lines = []
                for orig, char_data in data.items():
                    if isinstance(char_data, dict):
                        trans = char_data['translated']
                        gender = char_data['gender']
                        lines.append(f"{orig} : {trans} : {gender}")
                    else:
                        lines.append(f"{orig} : {char_data} : not_clear")
                self.character_tab.setPlainText("\n".join(lines))
            except Exception as e:
                self.character_tab.setPlainText(f"Error loading character file: {str(e)}")
        else:
            self.character_tab.setPlainText("No character data available yet.")

    def update_place_display(self):
        """Update place display tab."""
        if os.path.exists(self.current_place_file):
            try:
                import json
                with open(self.current_place_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                lines = []
                for orig, trans in data.items():
                    lines.append(f"{orig} : {trans}")
                self.place_tab.setPlainText("\n".join(lines))
            except Exception as e:
                self.place_tab.setPlainText(f"Error loading place file: {str(e)}")
        else:
            self.place_tab.setPlainText("No place data available yet.")

    def update_terms_display(self):
        """Update terms display tab."""
        if os.path.exists(self.current_terms_file):
            try:
                import json
                with open(self.current_terms_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                lines = []
                for orig, term_data in data.items():
                    if isinstance(term_data, dict):
                        trans = term_data['translated']
                        category = term_data['category']
                        lines.append(f"{orig} : {trans} : {category}")
                    else:
                        lines.append(f"{orig} : {term_data} : other")
                self.terms_tab.setPlainText("\n".join(lines))
            except Exception as e:
                self.terms_tab.setPlainText(f"Error loading terms file: {str(e)}")
        else:
            self.terms_tab.setPlainText("No terms data available yet.")

    def update_notes_display(self):
        """Update notes display tab."""
        if os.path.exists(self.current_notes_file):
            try:
                import json
                with open(self.current_notes_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                lines = []
                for key, note in data.items():
                    lines.append(f"{key} = {note}")
                self.notes_tab.setPlainText("\n".join(lines))
            except Exception as e:
                self.notes_tab.setPlainText(f"Error loading notes file: {str(e)}")
        else:
            self.notes_tab.setPlainText("No notes data available yet.")

    def update_raw_json_display(self, raw_json):
        """Update the raw JSON display with the latest response."""
        current_text = self.raw_json_tab.toPlainText()
        if current_text:
            separator = "\n" + "=" * 80 + "\n"
            new_text = current_text + separator + raw_json
        else:
            new_text = raw_json

        self.raw_json_tab.setPlainText(new_text)

        # Scroll to bottom
        cursor = self.raw_json_tab.textCursor()
        cursor.movePosition(cursor.End)
        self.raw_json_tab.setTextCursor(cursor)
