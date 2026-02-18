#!/usr/bin/env python3
"""
Test script to debug media generation failures.
Runs a single prompt and shows all output.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from repositories import PromptRepository
from executors import ImageWorkflowExecutor, AudioWorkflowExecutor
from models import ImagePromptData, LyricsPromptData

def main():
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'media_generator_config.json')
    config = load_config(config_path)

    # Initialize repository
    db_path = config['database']['path']
    repo = PromptRepository(db_path)

    # Reset a failed prompt back to pending for testing
    print("Resetting prompt #258 (image_prompt) to pending status...")
    repo.update_artifact_status(258, 'pending')

    # Get the prompt
    prompts = repo.get_pending_image_prompts(limit=1)

    if not prompts:
        print("No pending image prompts found. Trying lyrics prompts...")
        # Try lyrics instead
        print("Resetting prompt #259 (lyrics_prompt) to pending status...")
        repo.update_artifact_status(259, 'pending')
        prompts = repo.get_pending_lyrics_prompts(limit=1)

        if not prompts:
            print("ERROR: No pending prompts found!")
            return 1

        # Execute lyrics prompt
        prompt = prompts[0]
        print(f"\n{'=' * 80}")
        print(f"TESTING LYRICS PROMPT #{prompt.id}")
        print(f"{'=' * 80}")
        print(f"Prompt text: {prompt.prompt_text}")
        print()

        try:
            json_data = LyricsPromptData.from_json(prompt.get_json_prompt())
            executor = AudioWorkflowExecutor(config)

            print("Starting execution...")
            artifacts = executor.generate(prompt, json_data, progress_callback=print)

            print(f"\n✅ SUCCESS! Generated {len(artifacts)} artifact(s)")
            for artifact in artifacts:
                print(f"  - {artifact.file_path}")

            return 0

        except Exception as e:
            print(f"\n❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            return 1

    # Execute image prompt
    prompt = prompts[0]
    print(f"\n{'=' * 80}")
    print(f"TESTING IMAGE PROMPT #{prompt.id}")
    print(f"{'=' * 80}")
    print(f"Prompt text: {prompt.prompt_text}")
    print()

    try:
        json_data = ImagePromptData.from_json(prompt.get_json_prompt())
        executor = ImageWorkflowExecutor(config)

        print("Starting execution...")
        artifacts = executor.generate(prompt, json_data, progress_callback=print)

        print(f"\n✅ SUCCESS! Generated {len(artifacts)} artifact(s)")
        for artifact in artifacts:
            print(f"  - {artifact.file_path}")

        return 0

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
