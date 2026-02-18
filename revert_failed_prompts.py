#!/usr/bin/env python3
"""
Revert Failed Prompts

This script finds the most recent failed prompts (artifact_status='error')
and reverts them back to 'pending' status so they can be retried.
"""

import sqlite3
import sys
from pathlib import Path

# Database path from config
DB_PATH = "/Volumes/Tikbalang2TB/Users/tikbalang/Desktop/anthonys_musings.db"


def revert_failed_prompts(count: int = 2, auto_confirm: bool = False):
    """
    Revert the last N failed prompts back to pending status.

    Args:
        count: Number of failed prompts to revert (default: 2)
        auto_confirm: Skip confirmation prompt (default: False)
    """
    conn = None
    try:
        # Connect to database
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL")

        # Find the last N failed prompts
        cursor.execute("""
            SELECT
                id,
                prompt_text,
                prompt_type,
                artifact_status,
                error_message,
                created_at
            FROM prompts
            WHERE artifact_status = 'error'
            ORDER BY created_at DESC
            LIMIT ?
        """, (count,))

        failed_prompts = cursor.fetchall()

        if not failed_prompts:
            print("✓ No failed prompts found.")
            return

        print(f"\nFound {len(failed_prompts)} failed prompt(s):\n")
        print("=" * 80)

        for prompt in failed_prompts:
            print(f"ID: {prompt['id']}")
            print(f"Type: {prompt['prompt_type']}")
            print(f"Text: {prompt['prompt_text'][:60]}...")
            print(f"Error: {prompt['error_message'][:100] if prompt['error_message'] else 'None'}...")
            print(f"Created: {prompt['created_at']}")
            print("-" * 80)

        # Ask for confirmation (unless auto-confirm)
        if not auto_confirm:
            response = input(f"\nRevert these {len(failed_prompts)} prompt(s) to pending status? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Cancelled.")
                return
        else:
            print(f"\nAuto-confirming revert (--yes flag enabled)")

        # Update each prompt
        for prompt in failed_prompts:
            cursor.execute("""
                UPDATE prompts
                SET artifact_status = 'pending',
                    error_message = NULL
                WHERE id = ?
            """, (prompt['id'],))

        # Commit changes
        conn.commit()

        # Checkpoint WAL to ensure changes are visible
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        print(f"\n✓ Successfully reverted {len(failed_prompts)} prompt(s) to pending status.")
        print("\nYou can now retry them in the Media Generator app.")

    except sqlite3.Error as e:
        print(f"✗ Database error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)

    except Exception as e:
        print(f"✗ Error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # Parse arguments
    count = 2
    auto_confirm = False

    for arg in sys.argv[1:]:
        if arg in ['--yes', '-y']:
            auto_confirm = True
        else:
            try:
                count = int(arg)
            except ValueError:
                print(f"Usage: {sys.argv[0]} [count] [--yes]")
                print(f"  count: Number of failed prompts to revert (default: 2)")
                print(f"  --yes: Skip confirmation prompt")
                sys.exit(1)

    revert_failed_prompts(count, auto_confirm)
