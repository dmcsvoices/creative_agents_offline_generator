# 🎨 Creative Agents Offline Generator

<div align="center">

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![ComfyUI](https://img.shields.io/badge/ComfyUI-Compatible-purple.svg)
![Status](https://img.shields.io/badge/status-production-success.svg)

**Transform AI-generated prompts into stunning visual and audio content using ComfyUI workflows**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Architecture](#-architecture) • [Troubleshooting](#-troubleshooting)

</div>

---

## 🌟 Overview

Creative Agents Offline Generator is a **production-ready tkinter GUI application** that bridges the gap between AI prompt generation and media creation. It automatically processes pending prompts from your database and generates high-quality images and audio using ComfyUI Python workflows.

### 🎯 What It Does

- 📊 **Query pending prompts** from SQLite database
- 🖼️ **Generate images** using ComfyUI workflows (via Python scripts)
- 🎵 **Generate audio/songs** from lyrics prompts
- 💾 **Track artifacts** in database with metadata
- 🌐 **Frontend integration** for browsing generated content
- ⚡ **Real-time updates** with WAL checkpoint support

### 🎬 Perfect For

- Content creators automating media generation
- AI/ML researchers working with ComfyUI
- Developers building creative automation pipelines
- Artists exploring AI-assisted workflows

---

## ✨ Features

### 🖥️ Intuitive GUI
- **Dual-list interface** for image and song prompts
- **JSON preview panel** with syntax highlighting
- **Real-time status updates** during generation
- **Progress callbacks** with detailed logging
- **Error handling** with user-friendly messages

### 🔄 Seamless Integration
- **Phase 1**: Poets Service generates JSON prompts → Database
- **Phase 2**: This app generates media → Database artifacts
- **Frontend**: Browse page displays generated content

### 🛡️ Production Features
- **SQLite WAL mode** with automatic checkpointing
- **Docker container compatibility** for API visibility
- **Subprocess timeout handling** (15-minute default)
- **File path validation** and security checks
- **Comprehensive error logging** and recovery

### 🎨 Media Support
- **Images**: PNG (768x1024, 16:9, 21:9, custom)
- **Audio**: MP3, WAV, FLAC (song generation)
- **Metadata**: Full JSON metadata storage
- **Preview generation** for all media types

---

## 📋 Prerequisites

Before you begin, ensure you have:

- **Python 3.8+** installed
- **ComfyUI** installed and configured
- **SQLite database** with the required schema
- **Tkinter** (usually included with Python)
- **ComfyUI-to-Python-Extension** for workflow scripts

### Database Schema

Your SQLite database must have these tables:

```sql
-- Prompts table
CREATE TABLE prompts (
    id INTEGER PRIMARY KEY,
    prompt_text TEXT,
    prompt_type TEXT,  -- 'image_prompt' or 'lyrics_prompt'
    status TEXT,
    artifact_status TEXT,  -- 'pending', 'processing', 'ready', 'error'
    output_reference INTEGER,
    created_at TEXT,
    completed_at TEXT,
    error_message TEXT
);

-- Writings table (stores JSON content)
CREATE TABLE writings (
    id INTEGER PRIMARY KEY,
    content TEXT,  -- JSON string
    content_type TEXT,
    created_at TEXT
);

-- Artifacts table (stores generated media metadata)
CREATE TABLE prompt_artifacts (
    id INTEGER PRIMARY KEY,
    prompt_id INTEGER,
    artifact_type TEXT,  -- 'image' or 'audio'
    file_path TEXT,  -- Relative path from output_directory
    preview_path TEXT,
    metadata TEXT,  -- JSON string
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);
```

---

## 🚀 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/dmcsvoices/creative_agents_offline_generator.git
cd creative_agents_offline_generator
```

### Step 2: Install Dependencies

```bash
# Install Python dependencies (uses standard library)
# No external dependencies required!

# Optional: Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Configure the Application

```bash
# Copy the example configuration
cp media_generator_config.example.json media_generator_config.json

# Edit the configuration with your paths
nano media_generator_config.json  # or use your favorite editor
```

Update the following paths in `media_generator_config.json`:

```json
{
  "database": {
    "path": "/path/to/your/anthonys_musings.db",
    "timeout": 30.0
  },
  "comfyui": {
    "python": "/path/to/your/comfy_env/bin/python",
    "comfyui_directory": "/path/to/your/ComfyUI",
    "output_directory": "/path/to/output/directory",
    "timeout_seconds": 900
  },
  "workflows": {
    "image": {
      "script": "MultimediaWorkflow/Z-Image-Turbo-Tshirt_APP.py",
      "prompt_arg": "text7"
    },
    "song": {
      "script": "MultimediaWorkflow/song_workflow_placeholder.py",
      "prompt_arg": "lyrics_text"
    }
  }
}
```

### Step 4: Set Up ComfyUI Workflow Scripts

Your ComfyUI workflow scripts should be Python files generated using [ComfyUI-to-Python-Extension](https://github.com/pydn/ComfyUI-to-Python-Extension).

**For Image Generation:**
- Place your image workflow script in the ComfyUI directory
- Update `workflows.image.script` in config
- Ensure it accepts a `--text7` argument (or update `prompt_arg`)
- **Important**: Add `has_manager = False` at line 11 if using ComfyUI-SaveAsScript

**For Audio Generation:**
- Place your audio workflow script in the ComfyUI directory
- Update `workflows.song.script` in config
- Ensure it accepts a `--lyrics_text` argument (or update `prompt_arg`)

### Step 5: Create Output Directory

```bash
# Create the output directory structure
mkdir -p /path/to/output/directory/{image,audio}
```

### Step 6: Validate Configuration

```bash
python -c "from config import load_config, validate_config; \
           config = load_config('media_generator_config.json'); \
           issues = validate_config(config); \
           print('✓ Configuration valid!' if not issues else f'Issues: {issues}')"
```

---

## 🎮 Usage

### Launch the Application

```bash
python media_generator_app.py
```

### GUI Workflow

1. **View Pending Prompts**
   - Left panel: Image prompts
   - Right panel: Song/lyrics prompts
   - Each shows ID, creation date, and preview

2. **Select a Prompt**
   - Click any prompt to view full JSON details
   - Bottom panel shows complete prompt structure

3. **Generate Media**
   - Click **"Generate Selected"** button
   - Watch real-time status updates
   - Generation runs in background (may take 1-15 minutes)

4. **View Results**
   - Check status bar for completion
   - Click **"View Output Folder"** to see files
   - Refresh frontend to browse generated media

### Command-Line Validation

```bash
# Test database connection
python -c "from repositories import PromptRepository; \
           repo = PromptRepository('/path/to/db'); \
           prompts = repo.get_pending_image_prompts(); \
           print(f'Found {len(prompts)} pending prompts')"

# Test workflow execution (dry run)
python Z-Image-Turbo-Tshirt_APP.py \
    --text7 "A test prompt" \
    --output /tmp/test_output \
    --comfyui-directory /path/to/ComfyUI \
    --queue-size 1
```

---

## 🏗️ Architecture

### Project Structure

```
creative_agents_offline_generator/
├── media_generator_app.py          # Main tkinter GUI application
├── models.py                        # Data classes (PromptRecord, ArtifactRecord)
├── repositories.py                  # Database access layer
├── executors.py                     # Workflow execution layer
├── config.py                        # Configuration loader/validator
├── media_generator_config.json      # Your local configuration (gitignored)
├── media_generator_config.example.json  # Template configuration
├── Z-Image-Turbo-Tshirt_APP.py     # ComfyUI image workflow script
├── song_workflow_placeholder.py     # Placeholder for audio workflow
├── README.md                        # This file
├── FIXES_APPLIED.md                 # Troubleshooting documentation
└── .gitignore                       # Git ignore rules
```

### Data Flow

```
┌─────────────────┐
│ Poets Service   │ (Phase 1)
│ Generates JSON  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ SQLite Database │
│ - prompts       │
│ - writings      │
│ - artifacts     │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Media Generator │ (Phase 2 - This App)
│ - Query pending │
│ - Execute ComfyUI
│ - Save artifacts│
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Frontend/API    │
│ - Browse media  │
│ - Serve files   │
└─────────────────┘
```

### Workflow Execution

```python
# Simplified execution flow
def generate_image_prompt(prompt: PromptRecord):
    # 1. Update status
    prompt_repo.update_artifact_status(prompt.id, 'processing')

    # 2. Parse JSON
    json_data = ImagePromptData.from_json(prompt.get_json_prompt())

    # 3. Execute ComfyUI workflow
    executor = ImageWorkflowExecutor(config)
    artifacts = executor.generate(prompt, json_data)

    # 4. Save artifacts (with WAL checkpoint)
    for artifact in artifacts:
        artifact_repo.save_artifact(artifact)

    # 5. Update status (with WAL checkpoint)
    prompt_repo.update_artifact_status(prompt.id, 'ready')
```

---

## 🔧 Configuration Reference

### Database Settings

```json
"database": {
    "path": "Absolute path to SQLite database",
    "timeout": "Connection timeout in seconds (default: 30)"
}
```

### ComfyUI Settings

```json
"comfyui": {
    "python": "Path to Python executable in ComfyUI environment",
    "comfyui_directory": "Root directory of ComfyUI installation",
    "output_directory": "Where generated files are saved",
    "timeout_seconds": "Workflow execution timeout (default: 900)"
}
```

### Workflow Settings

```json
"workflows": {
    "image": {
        "script": "Relative path from comfyui_directory",
        "prompt_arg": "Argument name for prompt text (e.g., 'text7')"
    }
}
```

### UI Settings

```json
"ui": {
    "window_title": "Application window title",
    "window_width": "Window width in pixels (default: 1200)",
    "window_height": "Window height in pixels (default: 800)",
    "refresh_interval": "Auto-refresh interval in seconds (default: 30)"
}
```

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "NameError: name 'has_manager' is not defined"

**Solution:** Add this line to your workflow script (line 11):
```python
has_manager = False
```

See [FIXES_APPLIED.md](FIXES_APPLIED.md) Issue #1 for details.

#### 2. "Workflow script not found"

**Solution:** Check that the script path in config is relative to `comfyui_directory`:
```json
"script": "MultimediaWorkflow/Z-Image-Turbo-Tshirt_APP.py"
```

#### 3. "Frontend shows 'Image not available'"

**Possible causes:**
- Nginx configuration issue (see `FIXES_APPLIED.md` Issue #8)
- Wrong output directory path (see Issue #3)
- File permissions

**Solution:**
```bash
# Check file exists
ls -la /path/to/output/directory/image/*/

# Check API serves it
curl http://localhost:8000/api/media/image/201_20260107T164314/output.png

# Check frontend proxy
curl http://localhost:3001/api/media/image/201_20260107T164314/output.png
```

#### 4. "Docker container can't see artifacts"

**Cause:** SQLite WAL mode issue (see `FIXES_APPLIED.md` Issue #5)

**Solution:** Already implemented - automatic WAL checkpointing after writes

#### 5. "Browse page not showing new prompts"

**Cause:** Prompt type mismatch (see `FIXES_APPLIED.md` Issue #6)

**Solution:** Already implemented - API handles both "image" and "image_prompt" types

### Complete Troubleshooting Guide

See [FIXES_APPLIED.md](FIXES_APPLIED.md) for detailed documentation of all 8 issues encountered and resolved during development, including:
- Root cause analysis
- Code fixes applied
- Testing procedures
- Prevention strategies

---

## 📊 Performance

### Typical Generation Times

| Media Type | Resolution | Avg Time | Max Time |
|------------|-----------|----------|----------|
| Image | 768x1024 | 30-60s | 5 min |
| Image | 1024x1024 | 60-120s | 10 min |
| Audio | 3 min song | 120-300s | 15 min |

### Resource Requirements

- **RAM**: 4GB minimum, 8GB recommended
- **GPU**: NVIDIA GPU recommended for ComfyUI
- **Storage**: 10GB minimum for output files
- **CPU**: Multi-core processor for parallel processing

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Reporting Issues

1. Check [FIXES_APPLIED.md](FIXES_APPLIED.md) for known issues
2. Open a GitHub issue with:
   - Clear description
   - Steps to reproduce
   - Error messages
   - System information

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

- **ComfyUI Team** - For the amazing ComfyUI framework
- **ComfyUI-to-Python-Extension** - For workflow script generation
- **Poets Service** - For Phase 1 prompt generation integration
- **Claude Code** - For AI-assisted development and debugging

---

## 📞 Support

- 📧 **Issues**: [GitHub Issues](https://github.com/dmcsvoices/creative_agents_offline_generator/issues)
- 📖 **Documentation**: [FIXES_APPLIED.md](FIXES_APPLIED.md)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/dmcsvoices/creative_agents_offline_generator/discussions)

---

<div align="center">

**Made with ❤️ by the Creative Agents Team**

⭐ Star us on GitHub if this project helped you!

</div>
