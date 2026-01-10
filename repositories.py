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
        """Create database connection with row factory

        Returns:
            SQLite connection with row factory configured
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def get_pending_image_prompts(self, limit: int = 100) -> List[PromptRecord]:
        """Query all pending image prompts with their JSON content

        Args:
            limit: Maximum number of prompts to return

        Returns:
            List of PromptRecord objects with json_content populated
        """
        query = """
        SELECT
            p.id,
            p.prompt_text,
            p.prompt_type,
            p.status,
            p.artifact_status,
            p.output_reference,
            p.created_at,
            p.completed_at,
            p.error_message,
            w.id as writing_id,
            w.content as json_content
        FROM prompts p
        INNER JOIN writings w ON p.output_reference = w.id
        WHERE p.status = 'completed'
          AND p.artifact_status = 'pending'
          AND p.prompt_type = 'image_prompt'
          AND w.content_type = 'image_prompt'
        ORDER BY p.created_at ASC
        LIMIT ?
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

            return [self._row_to_prompt_record(row) for row in rows]

    def get_pending_lyrics_prompts(self, limit: int = 100) -> List[PromptRecord]:
        """Query all pending lyrics prompts with their JSON content

        Only returns 'lyrics_prompt' type (structured JSON format).
        Old 'song' type prompts used raw text format incompatible with ace_audio_workflow.

        Args:
            limit: Maximum number of prompts to return

        Returns:
            List of PromptRecord objects with json_content populated
        """
        query = """
        SELECT
            p.id,
            p.prompt_text,
            p.prompt_type,
            p.status,
            p.artifact_status,
            p.output_reference,
            p.created_at,
            p.completed_at,
            p.error_message,
            w.id as writing_id,
            w.content as json_content
        FROM prompts p
        INNER JOIN writings w ON p.output_reference = w.id
        WHERE p.status = 'completed'
          AND p.artifact_status = 'pending'
          AND p.prompt_type = 'lyrics_prompt'
          AND w.content_type = 'lyrics_prompt'
        ORDER BY p.created_at ASC
        LIMIT ?
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()

            return [self._row_to_prompt_record(row) for row in rows]

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
            cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")

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
        """Create database connection with row factory

        Returns:
            SQLite connection with row factory configured
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
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
            cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")

            return cursor.lastrowid

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
