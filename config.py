"""
Configuration loader and validator for Media Generator application.

Provides functions to:
- Load configuration from JSON file
- Validate required paths and settings
- Report configuration issues
"""

import json
import os
from typing import Dict, Any, List
from pathlib import Path


def load_config(path: str) -> Dict[str, Any]:
    """Load JSON configuration file

    Args:
        path: Path to configuration JSON file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    with open(path, 'r') as f:
        return json.load(f)


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate configuration and return list of issues

    Checks:
    - Database file exists
    - ComfyUI directory exists
    - Python executable exists
    - Image workflow script exists
    - Output directory can be created

    Args:
        config: Configuration dictionary

    Returns:
        List of issue strings (empty if no issues)
    """
    issues = []

    # Check database
    db_path = config.get('database', {}).get('path')
    if not db_path:
        issues.append("Database path not specified in config")
    elif not os.path.exists(db_path):
        issues.append(f"Database not found: {db_path}")

    # Check ComfyUI directory
    comfyui_dir = config.get('comfyui', {}).get('comfyui_directory')
    if not comfyui_dir:
        issues.append("ComfyUI directory not specified in config")
    elif not os.path.isdir(comfyui_dir):
        issues.append(f"ComfyUI directory not found: {comfyui_dir}")

    # Check Python executable
    python_exe = config.get('comfyui', {}).get('python')
    if not python_exe:
        issues.append("Python executable not specified in config")
    elif not os.path.exists(python_exe):
        issues.append(f"Python executable not found: {python_exe}")

    # Check image workflow script
    if comfyui_dir:
        image_script = config.get('workflows', {}).get('image', {}).get('script')
        if image_script:
            full_path = os.path.join(comfyui_dir, image_script)
            if not os.path.exists(full_path):
                issues.append(f"Image workflow script not found: {full_path}")
        else:
            issues.append("Image workflow script not specified in config")

    # Check output directory can be created
    output_dir = config.get('comfyui', {}).get('output_directory')
    if not output_dir:
        issues.append("Output directory not specified in config")
    else:
        # Try to create if it doesn't exist
        output_path = Path(output_dir)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            issues.append(f"Cannot create output directory {output_dir}: {e}")

    # Validate timeout is reasonable
    timeout = config.get('comfyui', {}).get('timeout_seconds')
    if timeout is None:
        issues.append("Workflow timeout not specified in config")
    elif not isinstance(timeout, (int, float)):
        issues.append(f"Workflow timeout must be a number, got {type(timeout)}")
    elif timeout <= 0:
        issues.append(f"Workflow timeout must be positive, got {timeout}")
    elif timeout > 3600:
        issues.append(f"Workflow timeout is very high ({timeout}s), consider reducing")

    return issues


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """Get a nested config value with dot notation

    Example:
        get_config_value(config, 'database.path')
        get_config_value(config, 'workflows.image.script', 'default.py')

    Args:
        config: Configuration dictionary
        key_path: Dot-separated key path (e.g., 'comfyui.python')
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    keys = key_path.split('.')
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value
