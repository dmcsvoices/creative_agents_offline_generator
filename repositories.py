"""
Database repositories for Media Generator application.

Provides database access classes:
- PromptRepository: Query and update prompts and writings tables
- ArtifactRepository: Manage prompt_artifacts table

Uses SQLite with WAL mode and proper timeout handling for concurrent access.
"""

import sqlite3
import json
from typing import List, Optional
from datetime import datetime
from models import PromptRecord, ArtifactRecord


class PromptRepository:
    """Database access layer for prompts and writings tables"""

    def __init__(self, db_path: str):
        """Initialize repository with database path

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Create database connection with row factory and WAL mode

        Returns:
            SQLite connection with row factory configured
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")

        return conn

    def get_pending_image_prompts(self, limit: int = 100) -> List[PromptRecord]:
        """Query all pending image prompts with ALL their writings

        Args:
            limit: Maximum number of prompts to return

        Returns:
            List of PromptRecord objects with all writings populated
        """
        # First get the prompts
        # NOTE: Only filter on artifact_status, not on status!
        # The 'status' field is the poets service's concern (whether IT completed)
        # The 'artifact_status' field is our concern (whether media needs generation)
        prompt_query = """
        SELECT
            p.id,
            p.prompt_text,
            p.prompt_type,
            p.status,
            p.artifact_status,
            p.output_reference,
            p.created_at,
            p.completed_at,
            p.error_message
        FROM prompts p
        WHERE p.artifact_status = 'pending'
          AND p.prompt_type = 'image_prompt'
        ORDER BY p.created_at ASC
        LIMIT ?
        """

        # Then get all writings for each prompt
        writings_query = """
        SELECT
            pw.writing_id,
            pw.writing_order,
            w.content,
            w.content_type,
            w.title
        FROM prompt_writings pw
        JOIN writings w ON pw.writing_id = w.id
        WHERE pw.prompt_id = ?
          AND w.content_type = 'image_prompt'
        ORDER BY pw.writing_order ASC
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Force checkpoint to see latest data from poets service
            try:
                cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.Error:
                # Non-critical, continue anyway
                pass

            # Get prompts
            cursor.execute(prompt_query, (limit,))
            prompt_rows = cursor.fetchall()

            results = []
            for prompt_row in prompt_rows:
                prompt_id = prompt_row['id']

                # Get all writings for this prompt
                cursor.execute(writings_query, (prompt_id,))
                writing_rows = cursor.fetchall()

                # Build writings list
                writings = []
                for w_row in writing_rows:
                    writings.append({
                        'writing_id': w_row['writing_id'],
                        'writing_order': w_row['writing_order'],
                        'content': w_row['content'],
                        'content_type': w_row['content_type'],
                        'title': w_row['title']
                    })

                # Create PromptRecord
                record = PromptRecord(
                    id=prompt_row['id'],
                    prompt_text=prompt_row['prompt_text'],
                    prompt_type=prompt_row['prompt_type'],
                    status=prompt_row['status'],
                    artifact_status=prompt_row['artifact_status'],
                    output_reference=prompt_row['output_reference'],
                    created_at=self._parse_datetime(prompt_row['created_at']),
                    completed_at=self._parse_datetime(prompt_row['completed_at']) if prompt_row['completed_at'] else None,
                    error_message=prompt_row['error_message'],
                    writings=writings,
                    # Legacy fields for backward compatibility
                    writing_id=writings[0]['writing_id'] if writings else None,
                    json_content=writings[0]['content'] if writings else None
                )

                results.append(record)

            return results

    def get_pending_lyrics_prompts(self, limit: int = 100) -> List[PromptRecord]:
        """Query all pending lyrics prompts with ALL their writings

        Only returns 'lyrics_prompt' type (structured JSON format).
        Old 'song' type prompts used raw text format incompatible with ace_audio_workflow.

        Args:
            limit: Maximum number of prompts to return

        Returns:
            List of PromptRecord objects with all writings populated
        """
        # First get the prompts
        # NOTE: Only filter on artifact_status, not on status!
        # The 'status' field is the poets service's concern (whether IT completed)
        # The 'artifact_status' field is our concern (whether media needs generation)
        prompt_query = """
        SELECT
            p.id,
            p.prompt_text,
            p.prompt_type,
            p.status,
            p.artifact_status,
            p.output_reference,
            p.created_at,
            p.completed_at,
            p.error_message
        FROM prompts p
        WHERE p.artifact_status = 'pending'
          AND p.prompt_type = 'lyrics_prompt'
        ORDER BY p.created_at ASC
        LIMIT ?
        """

        # Then get all writings for each prompt
        writings_query = """
        SELECT
            pw.writing_id,
            pw.writing_order,
            w.content,
            w.content_type,
            w.title
        FROM prompt_writings pw
        JOIN writings w ON pw.writing_id = w.id
        WHERE pw.prompt_id = ?
          AND w.content_type = 'lyrics_prompt'
        ORDER BY pw.writing_order ASC
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Force checkpoint to see latest data from poets service
            try:
                checkpoint_result = cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                checkpoint_info = checkpoint_result.fetchone()
                print(f"[DEBUG] WAL checkpoint (lyrics): {checkpoint_info}")
            except sqlite3.Error as e:
                # Non-critical, continue anyway
                print(f"[DEBUG] WAL checkpoint failed: {e}")

            # Debug: Check total lyrics_prompt records regardless of status
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as status_completed,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as status_failed,
                       SUM(CASE WHEN artifact_status = 'pending' THEN 1 ELSE 0 END) as artifact_pending,
                       SUM(CASE WHEN artifact_status = 'ready' THEN 1 ELSE 0 END) as artifact_ready
                FROM prompts
                WHERE prompt_type = 'lyrics_prompt'
            """)
            stats = cursor.fetchone()
            print(f"[DEBUG] Lyrics prompts in DB: total={stats['total']}")
            print(f"        Status breakdown: completed={stats['status_completed']}, failed={stats['status_failed']}")
            print(f"        Artifact breakdown: pending={stats['artifact_pending']}, ready={stats['artifact_ready']}")

            # Debug: Show recent lyrics prompts with their statuses
            cursor.execute("""
                SELECT id, prompt_text, status, artifact_status, created_at
                FROM prompts
                WHERE prompt_type = 'lyrics_prompt'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent = cursor.fetchall()
            print(f"[DEBUG] Recent lyrics prompts:")
            for r in recent:
                print(f"  - ID={r['id']}, status='{r['status']}', artifact_status='{r['artifact_status']}', created={r['created_at']}, text='{r['prompt_text'][:50]}...'")

            # Get prompts
            cursor.execute(prompt_query, (limit,))
            prompt_rows = cursor.fetchall()

            print(f"[DEBUG] Query returned {len(prompt_rows)} lyrics prompts matching criteria (artifact_status='pending')")

            results = []
            for prompt_row in prompt_rows:
                prompt_id = prompt_row['id']

                # Get all writings for this prompt
                cursor.execute(writings_query, (prompt_id,))
                writing_rows = cursor.fetchall()

                print(f"[DEBUG] Prompt #{prompt_id} has {len(writing_rows)} writings")

                # Build writings list
                writings = []
                for w_row in writing_rows:
                    writings.append({
                        'writing_id': w_row['writing_id'],
                        'writing_order': w_row['writing_order'],
                        'content': w_row['content'],
                        'content_type': w_row['content_type'],
                        'title': w_row['title']
                    })

                # Create PromptRecord
                record = PromptRecord(
                    id=prompt_row['id'],
                    prompt_text=prompt_row['prompt_text'],
                    prompt_type=prompt_row['prompt_type'],
                    status=prompt_row['status'],
                    artifact_status=prompt_row['artifact_status'],
                    output_reference=prompt_row['output_reference'],
                    created_at=self._parse_datetime(prompt_row['created_at']),
                    completed_at=self._parse_datetime(prompt_row['completed_at']) if prompt_row['completed_at'] else None,
                    error_message=prompt_row['error_message'],
                    writings=writings,
                    # Legacy fields for backward compatibility
                    writing_id=writings[0]['writing_id'] if writings else None,
                    json_content=writings[0]['content'] if writings else None
                )

                results.append(record)

            return results

    def update_artifact_status(
        self,
        prompt_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update prompt artifact_status and optionally error_message

        Args:
            prompt_id: Prompt ID to update
            status: New artifact_status ('pending', 'processing', 'ready', 'error')
            error_message: Optional error message (only used with 'error' status)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if error_message:
                cursor.execute("""
                    UPDATE prompts
                    SET artifact_status = ?, error_message = ?
                    WHERE id = ?
                """, (status, error_message, prompt_id))
            else:
                cursor.execute("""
                    UPDATE prompts
                    SET artifact_status = ?
                    WHERE id = ?
                """, (status, prompt_id))

            conn.commit()

            # Checkpoint WAL to ensure Docker containers can see changes
            try:
                cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.Error:
                # Non-critical operation - log but don't fail
                pass

    def reset_stale_processing_prompts(self, timeout_minutes: int = 30) -> int:
        """
        Reset prompts stuck in 'processing' status back to 'pending'.

        This handles cases where the app crashed during generation.

        Args:
            timeout_minutes: How long before considering 'processing' stale

        Returns:
            Number of prompts reset
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Find prompts that have been processing for too long
            # Use processed_at since that's when status was set to 'processing'
            cursor.execute("""
                UPDATE prompts
                SET artifact_status = 'pending',
                    error_message = 'Reset from stale processing state'
                WHERE artifact_status = 'processing'
                  AND processed_at IS NOT NULL
                  AND processed_at < datetime('now', '-' || ? || ' minutes')
            """, (timeout_minutes,))

            count = cursor.rowcount
            conn.commit()

            return count

    def _row_to_prompt_record(self, row: sqlite3.Row) -> PromptRecord:
        """Convert database row to PromptRecord object

        Args:
            row: SQLite row from query

        Returns:
            PromptRecord with all fields populated
        """
        return PromptRecord(
            id=row['id'],
            prompt_text=row['prompt_text'],
            prompt_type=row['prompt_type'],
            status=row['status'],
            artifact_status=row['artifact_status'],
            output_reference=row['output_reference'],
            created_at=self._parse_datetime(row['created_at']),
            completed_at=self._parse_datetime(row['completed_at']) if row['completed_at'] else None,
            error_message=row['error_message'],
            writing_id=row['writing_id'],
            json_content=row['json_content']
        )

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string from database

        Handles various datetime formats from SQLite.

        Args:
            dt_str: Datetime string

        Returns:
            datetime object
        """
        # Try ISO format first
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except ValueError:
            pass

        # Try common SQLite format
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass

        # Fallback: try with milliseconds
        try:
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            # Last resort: return current time
            return datetime.now()


class ArtifactRepository:
    """Database access layer for prompt_artifacts table"""

    def __init__(self, db_path: str):
        """Initialize repository with database path

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        """Create database connection with row factory and WAL mode

        Returns:
            SQLite connection with row factory configured
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")

        return conn

    def save_artifact(self, artifact: ArtifactRecord) -> int:
        """Insert artifact record into database

        Args:
            artifact: ArtifactRecord to save

        Returns:
            ID of inserted artifact record
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO prompt_artifacts (
                    prompt_id,
                    artifact_type,
                    file_path,
                    preview_path,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
                artifact.prompt_id,
                artifact.artifact_type,
                artifact.file_path,
                artifact.preview_path,
                json.dumps(artifact.metadata)
            ))

            conn.commit()

            # Checkpoint WAL to ensure Docker containers can see changes
            try:
                cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.Error:
                # Non-critical operation - log but don't fail
                pass

            return cursor.lastrowid

    def save_artifacts_atomic(
        self,
        prompt_id: int,
        artifacts: List[ArtifactRecord],
        final_status: str = 'ready'
    ):
        """
        Atomically save all artifacts and update prompt status.

        All operations succeed together or fail together (rollback on error).

        Args:
            prompt_id: Prompt ID
            artifacts: List of ArtifactRecord objects to save
            final_status: Final artifact_status ('ready' or 'error')

        Raises:
            Exception if transaction fails (will trigger rollback)
        """
        from db_utils import db_transaction
        import json

        with db_transaction(self.db_path) as conn:
            cursor = conn.cursor()

            # Step 1: Insert all artifacts
            for artifact in artifacts:
                cursor.execute("""
                    INSERT INTO prompt_artifacts (
                        prompt_id,
                        artifact_type,
                        file_path,
                        preview_path,
                        metadata,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    artifact.prompt_id,
                    artifact.artifact_type,
                    artifact.file_path,
                    artifact.preview_path,
                    json.dumps(artifact.metadata) if artifact.metadata else None
                ))

            # Step 2: Update status to final state
            cursor.execute("""
                UPDATE prompts
                SET artifact_status = ?
                WHERE id = ?
            """, (final_status, prompt_id))

            # All operations succeed together (auto-commits)
            # Or all fail together (auto-rollback)

        # Checkpoint after successful transaction
        from db_utils import force_wal_checkpoint
        force_wal_checkpoint(self.db_path, mode="RESTART")

    def get_artifacts_for_prompt(self, prompt_id: int) -> List[ArtifactRecord]:
        """Get all artifacts for a specific prompt

        Args:
            prompt_id: Prompt ID to query artifacts for

        Returns:
            List of ArtifactRecord objects
        """
        query = """
        SELECT
            id,
            prompt_id,
            artifact_type,
            file_path,
            preview_path,
            metadata,
            created_at
        FROM prompt_artifacts
        WHERE prompt_id = ?
        ORDER BY created_at DESC
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (prompt_id,))
            rows = cursor.fetchall()

            return [self._row_to_artifact_record(row) for row in rows]

    def _row_to_artifact_record(self, row: sqlite3.Row) -> ArtifactRecord:
        """Convert database row to ArtifactRecord object

        Args:
            row: SQLite row from query

        Returns:
            ArtifactRecord with all fields populated
        """
        # Parse metadata JSON
        metadata = {}
        if row['metadata']:
            try:
                metadata = json.loads(row['metadata'])
            except json.JSONDecodeError:
                metadata = {}

        # Parse created_at
        created_at = None
        if row['created_at']:
            try:
                created_at = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            except ValueError:
                try:
                    created_at = datetime.strptime(row['created_at'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    created_at = datetime.now()

        return ArtifactRecord(
            id=row['id'],
            prompt_id=row['prompt_id'],
            artifact_type=row['artifact_type'],
            file_path=row['file_path'],
            preview_path=row['preview_path'],
            metadata=metadata,
            created_at=created_at
        )
