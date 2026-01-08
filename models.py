"""
Data models for Media Generator application.

Defines dataclasses for:
- PromptRecord: Database prompt records with JSON content
- ImagePromptData: Parsed image prompt JSON structure
- LyricsPromptData: Parsed lyrics prompt JSON structure
- ArtifactRecord: Generated artifact metadata
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import json


@dataclass
class PromptRecord:
    """Database prompt record with JSON content from writings table"""

    id: int
    prompt_text: str
    prompt_type: str  # 'image_prompt' or 'lyrics_prompt'
    status: str  # 'completed', 'failed', etc.
    artifact_status: str  # 'pending', 'processing', 'ready', 'error'
    output_reference: Optional[int]  # FK to writings.id
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    json_content: Optional[str]  # Joined from writings.content
    writing_id: Optional[int]  # writings.id

    @property
    def is_pending(self) -> bool:
        """Check if prompt is pending media generation"""
        return (
            self.status == 'completed'
            and self.artifact_status == 'pending'
            and self.json_content is not None
        )

    def get_json_prompt(self) -> Dict[str, Any]:
        """Parse JSON content from writings table"""
        if not self.json_content:
            return {}
        try:
            return json.loads(self.json_content)
        except json.JSONDecodeError:
            return {}


@dataclass
class ImagePromptData:
    """Parsed image prompt JSON structure"""

    prompt: str
    negative_prompt: str
    style_tags: List[str]
    aspect_ratio: str
    quality: str
    mood: str
    subject: str
    background: str
    lighting: str

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'ImagePromptData':
        """Parse from writings.content JSON

        Expected structure:
        {
            "prompt": "...",
            "negative_prompt": "...",
            "style_tags": [...],
            "technical_params": {
                "aspect_ratio": "16:9",
                "quality": "high",
                "mood": "..."
            },
            "composition": {
                "subject": "...",
                "background": "...",
                "lighting": "..."
            }
        }
        """
        tech = data.get('technical_params', {})
        comp = data.get('composition', {})

        return cls(
            prompt=data.get('prompt', ''),
            negative_prompt=data.get('negative_prompt', ''),
            style_tags=data.get('style_tags', []),
            aspect_ratio=tech.get('aspect_ratio', '16:9'),
            quality=tech.get('quality', 'high'),
            mood=tech.get('mood', ''),
            subject=comp.get('subject', ''),
            background=comp.get('background', ''),
            lighting=comp.get('lighting', '')
        )


@dataclass
class LyricsPromptData:
    """Parsed lyrics prompt JSON structure"""

    title: str
    genre: str
    mood: str
    tempo: str
    structure: List[Dict[str, Any]]
    key: str
    time_signature: str
    vocal_style: str
    instrumentation: List[str]

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'LyricsPromptData':
        """Parse from writings.content JSON

        Expected structure:
        {
            "title": "...",
            "genre": "...",
            "mood": "...",
            "tempo": "...",
            "structure": [
                {
                    "type": "verse",
                    "number": 1,
                    "lyrics": "..."
                },
                {
                    "type": "chorus",
                    "lyrics": "..."
                }
            ],
            "metadata": {
                "key": "D major",
                "time_signature": "4/4",
                "vocal_style": "...",
                "instrumentation": [...]
            }
        }
        """
        meta = data.get('metadata', {})

        return cls(
            title=data.get('title', ''),
            genre=data.get('genre', ''),
            mood=data.get('mood', ''),
            tempo=data.get('tempo', ''),
            structure=data.get('structure', []),
            key=meta.get('key', ''),
            time_signature=meta.get('time_signature', '4/4'),
            vocal_style=meta.get('vocal_style', ''),
            instrumentation=meta.get('instrumentation', [])
        )

    def get_full_lyrics(self) -> str:
        """Combine all lyrics sections into single text

        Returns formatted lyrics with section markers:
        [VERSE]
        lyrics...

        [CHORUS]
        lyrics...
        """
        lyrics_parts = []
        for section in self.structure:
            section_type = section.get('type', '').upper()
            lyrics = section.get('lyrics', '')
            lyrics_parts.append(f"[{section_type}]\n{lyrics}\n")
        return "\n".join(lyrics_parts)


@dataclass
class ArtifactRecord:
    """Generated artifact metadata for database storage"""

    id: Optional[int]  # Set by database after insert
    prompt_id: int  # FK to prompts.id
    artifact_type: str  # 'image' or 'audio'
    file_path: str  # Relative path: 'poets/image/123_20260107/file.png'
    preview_path: Optional[str]  # For images: same as file_path; for audio: None
    metadata: Dict[str, Any]  # JSON metadata (prompt, params, generation details)
    created_at: Optional[datetime] = None  # Set by database
