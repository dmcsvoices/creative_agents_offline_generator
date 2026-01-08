#!/usr/bin/env python3
"""
Automated Media Generator Service

Monitors database for pending media prompts and generates them automatically.
Runs every 5 minutes via launchd.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from models import PromptRecord, ImagePromptData, LyricsPromptData
from repositories import PromptRepository, ArtifactRepository
from executors import ImageWorkflowExecutor, AudioWorkflowExecutor
from config import load_config, validate_config


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('media_generator_service.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def process_pending_prompts(config, logger):
    """Process all pending media prompts"""
    db_path = config['database']['path']
    prompt_repo = PromptRepository(db_path)
    artifact_repo = ArtifactRepository(db_path)

    # Get pending image prompts
    image_prompts = prompt_repo.get_pending_image_prompts(limit=10)
    logger.info(f"Found {len(image_prompts)} pending image prompts")

    # Get pending lyrics prompts
    lyrics_prompts = prompt_repo.get_pending_lyrics_prompts(limit=10)
    logger.info(f"Found {len(lyrics_prompts)} pending lyrics prompts")

    if not image_prompts and not lyrics_prompts:
        logger.info("No pending media prompts found")
        return 0

    # Process image prompts
    if image_prompts:
        image_executor = ImageWorkflowExecutor(config)
        for prompt in image_prompts:
            try:
                logger.info(f"Processing image prompt #{prompt.id}")
                prompt_repo.update_artifact_status(prompt.id, 'processing')

                json_data = ImagePromptData.from_json(prompt.get_json_prompt())
                artifacts = image_executor.generate(prompt, json_data)

                for artifact in artifacts:
                    artifact_repo.save_artifact(artifact)

                prompt_repo.update_artifact_status(prompt.id, 'ready')
                logger.info(f"Successfully generated {len(artifacts)} image(s) for prompt #{prompt.id}")

            except Exception as e:
                logger.error(f"Failed to process image prompt #{prompt.id}: {e}")
                prompt_repo.update_artifact_status(prompt.id, 'error', str(e))

    # Process lyrics prompts
    if lyrics_prompts:
        audio_executor = AudioWorkflowExecutor(config)
        for prompt in lyrics_prompts:
            try:
                logger.info(f"Processing lyrics prompt #{prompt.id}")
                prompt_repo.update_artifact_status(prompt.id, 'processing')

                json_data = LyricsPromptData.from_json(prompt.get_json_prompt())
                artifacts = audio_executor.generate(prompt, json_data)

                for artifact in artifacts:
                    artifact_repo.save_artifact(artifact)

                prompt_repo.update_artifact_status(prompt.id, 'ready')
                logger.info(f"Successfully generated {len(artifacts)} audio file(s) for prompt #{prompt.id}")

            except Exception as e:
                logger.error(f"Failed to process lyrics prompt #{prompt.id}: {e}")
                prompt_repo.update_artifact_status(prompt.id, 'error', str(e))

    total_processed = len(image_prompts) + len(lyrics_prompts)
    return total_processed


def main():
    """Main entry point"""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Media Generator Service - Starting")
    logger.info("=" * 60)

    # Load config
    config_path = Path(__file__).parent / 'media_generator_config.json'
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        return 1

    try:
        config = load_config(str(config_path))

        # Validate config
        issues = validate_config(config)
        if issues:
            logger.error("Configuration issues:")
            for issue in issues:
                logger.error(f"  - {issue}")
            return 1

        # Process pending prompts
        processed = process_pending_prompts(config, logger)
        logger.info(f"Processed {processed} prompt(s)")
        logger.info("Media Generator Service - Complete")
        return 0

    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
