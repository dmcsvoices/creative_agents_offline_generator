#!/usr/bin/env python3
"""
Unfail Prompts Script

Resets failed prompts back to 'pending' status so they can be retried.
"""

import sqlite3
import sys

def unfail_prompts(db_path: str, prompt_ids: list[int]):
    """Reset failed prompts back to pending status

    Args:
        db_path: Path to SQLite database
        prompt_ids: List of prompt IDs to unfail
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL")

        # Show current status
        print("Current status of prompts:")
        print("-" * 80)
        for prompt_id in prompt_ids:
            cursor.execute("""
                SELECT id, prompt_type, artifact_status, error_message, created_at
                FROM prompts
                WHERE id = ?
            """, (prompt_id,))
            row = cursor.fetchone()

            if row:
                print(f"ID {row['id']} ({row['prompt_type']})")
                print(f"  Status: {row['artifact_status']}")
                print(f"  Error: {row['error_message'][:100] if row['error_message'] else 'None'}...")
                print()
            else:
                print(f"ID {prompt_id} - NOT FOUND")
                print()

        # Confirm action
        response = input(f"\nReset these {len(prompt_ids)} prompt(s) to 'pending'? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return

        # Reset to pending
        for prompt_id in prompt_ids:
            cursor.execute("""
                UPDATE prompts
                SET artifact_status = 'pending',
                    error_message = NULL
                WHERE id = ?
            """, (prompt_id,))

            print(f"✓ Reset prompt #{prompt_id} to pending")

        conn.commit()

        # Force checkpoint to persist changes
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        print(f"\n✓ Successfully unfailed {len(prompt_ids)} prompt(s)")
        print("They will appear in the media generator app when you refresh.")

    finally:
        conn.close()


if __name__ == '__main__':
    db_path = "/Volumes/Tikbalang2TB/Users/tikbalang/Desktop/anthonys_musings.db"

    # Last two failed prompts (image and song)
    prompt_ids = [258, 259]

    unfail_prompts(db_path, prompt_ids)
