# EpubTranslate

A powerful desktop application for translating EPUB ebooks using AI language models, with advanced context management and progress tracking.

## Model Optimization

This application has been optimized for **DeepSeek v3.1** and **DeepSeek v3.2**, offering the best price-to-performance ratio for EPUB translation. Users can explore other model options through OpenRouter or custom endpoints, but DeepSeek models are recommended for optimal results and cost efficiency.

## Features

### Core Translation Capabilities
- **AI-Powered Translation**: Translate entire EPUB books using state-of-the-art language models via OpenRouter or custom endpoints
- **Intelligent Chunking**: Automatically splits large chapters into manageable chunks based on token count
- **Multi-Provider Fallback**: Configurable provider list with automatic fallback if one fails
- **Streaming Translation**: Real-time display of translation progress as it happens
- **Resume Support**: Save and resume translation sessions at any time

### Context Management
Maintain translation consistency across your entire book:
- **Character Database**: Track character names with gender information for consistent pronouns
- **Place Names**: Ensure location names remain consistent throughout the translation
- **Terminology**: Manage specialized terms (spells, weapons, skills, items, etc.) with categories
- **Translation Notes**: Optional note-taking system for translator preferences and decisions

### Advanced Features
- **Chapter Overview**: Visual table showing translation status, file sizes, and timestamps for all chapters
- **Previous Context**: Send previous chapters/chunks as context for better translation continuity
- **Concurrent Workers**: Process multiple chapters simultaneously (limited to 1 when context mode is enabled)
- **EPUB Rebuilding**: Automatically reconstructs translated EPUB with:
  - AI-translated table of contents
  - Preserved original structure and formatting
  - Proper language metadata
- **Power Steering Mode**: Toggle between different instruction placement strategies for the AI model
- **Flexible Chapter Selection**: Choose specific chapters by range or CSV list

## Screenshots

![EpubTranslate Main Interface](screenshots/screenshot_1.png)

The application features a comprehensive PyQt5-based GUI with:
- File selection and EPUB parsing
- Model and provider selection with live API fetching
- Multiple tabs for settings, context data, progress tracking, and logs
- Color-coded chapter status indicators
- Real-time translation preview

## Installation

### Prerequisites
- Python 3.8 or higher
- An API key from [OpenRouter](https://openrouter.ai/) or a custom LLM endpoint

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/BeetleBonsai798/EpubTranslate.git
   cd EpubTranslate
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv .venv

   # On Windows
   .venv\Scripts\activate

   # On macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API keys**
   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Edit .env and add your API keys
   # OPENROUTER_API_KEY=your_openrouter_api_key_here
   # CUSTOM_ENDPOINT_URL=https://your-custom-endpoint.com/v1
   # CUSTOM_ENDPOINT_KEY=your_custom_endpoint_key_here
   ```

5. **Configure translation settings** (optional)
   ```bash
   # Copy the example config file
   cp translator_config.json.example translator_config.json

   # Edit translator_config.json to customize default settings
   ```

**Note:** The `prompts_config.json` file contains AI prompts and translation instructions. It's already configured and typically doesn't need modification unless you want to customize the translation style or prompts.

## Usage

### Starting the Application

```bash
python main.py
```

### Basic Workflow

1. **Load EPUB File**
   - Click "Browse" to select your EPUB file
   - The application will automatically parse chapters

2. **Configure API Settings**
   - Select OpenRouter or Custom Endpoint
   - Choose your preferred AI model
   - Select providers (for OpenRouter)

3. **Select Chapters**
   - Choose "Range" or "CSV" mode
   - Specify which chapters to translate

4. **Configure Translation Settings**
   - Adjust temperature, max tokens, and other parameters
   - Enable/disable context mode, notes mode, etc.
   - Set concurrent workers (limited to 1 with context mode)

5. **Start Translation**
   - Click "Start Translation"
   - Monitor progress in the Chapter Overview tab
   - View real-time translation in the Raw JSON Output tab
   - Check individual worker logs for debugging

6. **Build Final EPUB**
   - Once all chapters are completed, click "Build EPUB"
   - The application will translate the table of contents
   - Final EPUB will be saved in the output directory

### Output Structure

For each translated EPUB, a directory is created:

```
{epub_name}_translated/
├── xhtml/
│   ├── 1.xhtml          # Translated chapter files
│   ├── 2.xhtml
│   └── ...
├── context/
│   ├── {epub_name}_characters.json
│   ├── {epub_name}_places.json
│   ├── {epub_name}_terms.json
│   └── {epub_name}_notes.json
└── {epub_name}_translated.epub  # Final translated book
```

## Configuration

The application uses three configuration files:
- **`.env`**: API keys and endpoints (create from `.env.example`)
- **`translator_config.json`**: Translation settings and preferences (create from `translator_config.json.example`)
- **`prompts_config.json`**: AI prompts and instructions (already included, rarely needs modification)

### Environment Variables (.env)

```bash
# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Custom Endpoint Configuration (e.g., chutes.ai)
CUSTOM_ENDPOINT_URL=https://llm.chutes.ai/v1
CUSTOM_ENDPOINT_KEY=your_custom_endpoint_key_here
```

### Translation Settings (translator_config.json)

```json
{
  "use_custom_endpoint": false,
  "custom_endpoint_model": "deepseek-ai/DeepSeek-V3.2-Exp",
  "model": "deepseek/deepseek-v3.2-exp",
  "chunk_tokens": 7000,
  "temperature": 0.9,
  "max_tokens": 12000,
  "frequency_penalty": 0.0,
  "top_p": 0.95,
  "top_k": 0,
  "timeout": 10.0,
  "retries_per_provider": 2,
  "selected_providers": [
    "novita/fp8",
    "siliconflow/fp8",
    "deepinfra/fp4",
    "gmicloud/fp8"
  ],
  "context_mode": true,
  "notes_mode": false,
  "power_steering": false,
  "send_previous": false,
  "previous_chapters": 1,
  "send_previous_chunks": false,
  "compress_paragraphs": false,
  "concurrent_workers": 1,
  "chapter_selection_mode": "range",
  "start_chapter": "1",
  "end_chapter": "1",
  "csv_chapters": "",
  "last_epub_path": ""
}
```

## Key Parameters Explained

- **chunk_tokens**: Maximum tokens per translation chunk (default: 7000)
- **temperature**: Controls randomness in translation (0.0-2.0, higher = more creative)
- **max_tokens**: Maximum tokens in the response
- **context_mode**: Enable to maintain character/place/term consistency
- **power_steering**: Places JSON format instructions in user prompt vs system prompt
- **send_previous**: Include previous chapters as context
- **send_previous_chunks**: Include previous chunks from current chapter as context
- **concurrent_workers**: Number of chapters to process simultaneously

## Tips for Best Results

1. **Enable Context Mode**: For novels and fiction, context mode ensures consistent character names and terminology
2. **Start with Lower Temperature**: Use 0.7-0.9 for more consistent translations; increase for more creative output
3. **Choose Appropriate Models**: Larger models generally produce better translations but cost more
4. **Use Provider Fallback**: Configure multiple providers to ensure translation continues even if one fails
5. **Monitor Token Usage**: Keep chunk_tokens reasonable (5000-8000) to avoid timeouts
6. **Review Context Data**: Periodically check the Characters/Places/Terms tabs to ensure accuracy

## Logging

Logs are stored in `~/.epub-translator/logs/translator.log`

Individual worker logs are also displayed in the GUI for debugging.

## Troubleshooting

### Common Issues

**Translation fails with timeout errors:**
- Reduce `chunk_tokens` value
- Increase `timeout` value
- Try a different provider

**Inconsistent character names:**
- Enable `context_mode`
- Manually review and edit the Characters database in the GUI
- Ensure `concurrent_workers` is set to 1 when using context mode

**EPUB build fails:**
- Ensure all chapters are completed (green status in Chapter Overview)
- Check that output directory is writable
- Review logs for specific errors

**API key errors:**
- Verify `.env` file exists and contains valid API keys
- Check that API keys have sufficient credits
- Ensure endpoint URLs are correct

## Technical Details

### Technology Stack
- **GUI**: PyQt5
- **EPUB Handling**: ebooklib
- **HTML/Markdown Conversion**: pypandoc, BeautifulSoup4
- **Token Counting**: tiktoken (OpenAI tokenizer)
- **API Client**: openai (compatible with OpenRouter and custom endpoints)

### Architecture
- **Main Window** (`src/translator/ui/main_window.py`): PyQt5 application interface
- **Translation Worker** (`src/translator/core/translation_worker.py`): Handles chapter translation with streaming
- **Context Manager** (`src/translator/core/context_manager.py`): Manages character/place/term databases
- **EPUB Rebuilder** (`src/translator/core/epub_rebuilder.py`): Reconstructs translated EPUB files
- **Config Manager** (`src/translator/config/config_manager.py`): Handles configuration and environment variables

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with OpenRouter API for multi-provider LLM access
- Uses OpenAI-compatible API standards for maximum compatibility
- Developed in collaboration with Claude (Anthropic)

---

**Made with Claude**

*Developed by BEETLEBONSAI PRIVATE LIMITED*
