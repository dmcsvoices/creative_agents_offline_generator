"""
Workflow executors for Media Generator application.

Provides classes to execute ComfyUI workflow scripts:
- ComfyUIWorkflowExecutor: Base class with common functionality
- ImageWorkflowExecutor: Execute image generation workflows
- AudioWorkflowExecutor: Execute audio/song generation workflows

Handles subprocess execution, file detection, and artifact creation.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from models import PromptRecord, ImagePromptData, LyricsPromptData, ArtifactRecord

_LOG_PATH = Path(__file__).parent / 'generation_errors.log'


def _write_generation_log(prompt_id: int, result) -> None:
    """Append subprocess result to persistent log file for post-mortem debugging."""
    with open(_LOG_PATH, 'a') as log_file:
        log_file.write(f"\n{'='*80}\n")
        log_file.write(f"Prompt #{prompt_id} — {datetime.now().isoformat()}\n")
        log_file.write(f"Return code: {result.returncode}\n")
        if result.stderr:
            log_file.write(f"STDERR:\n{result.stderr}\n")
        if result.returncode != 0 and result.stdout:
            log_file.write(f"STDOUT:\n{result.stdout}\n")


class ComfyUIWorkflowExecutor:
    """Base class for executing ComfyUI workflows via subprocess"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize executor with configuration

        Args:
            config: Configuration dictionary with comfyui settings
        """
        self.python_executable = config['comfyui']['python']
        self.comfyui_directory = Path(config['comfyui']['comfyui_directory'])
        self.output_root = Path(config['comfyui']['output_directory'])
        self.timeout_seconds = config['comfyui']['timeout_seconds']

    def _create_output_directory(self, prompt_id: int, artifact_type: str) -> Path:
        """Create timestamped output directory for generation

        Creates directory structure: output_root / artifact_type / {prompt_id}_{timestamp}

        Args:
            prompt_id: Prompt ID for naming
            artifact_type: 'image' or 'audio'

        Returns:
            Path to created output directory
        """
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        output_dir = self.output_root / artifact_type / f"{prompt_id}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _get_relative_path(self, full_path: Path) -> str:
        """Convert absolute path to relative path from output root

        The database stores paths relative to the output_directory configured.
        Since output_directory is /Volumes/Tikbalang2TB/ComfyUIOutput,
        we need paths relative to that directory.

        Example:
            Input: /Volumes/Tikbalang2TB/ComfyUIOutput/image/123_20260107/file.png
            Output: image/123_20260107/file.png

        Args:
            full_path: Absolute path to file

        Returns:
            Relative path string
        """
        return str(full_path.relative_to(self.output_root))


class ImageWorkflowExecutor(ComfyUIWorkflowExecutor):
    """Execute image generation workflows"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize image workflow executor

        Args:
            config: Configuration dictionary
        """
        super().__init__(config)

        script_path = config['workflows']['image']['script']
        self.workflow_script = self.comfyui_directory / script_path
        self.prompt_arg = config['workflows']['image']['prompt_arg']

    def generate(
        self,
        prompt: PromptRecord,
        json_data: ImagePromptData,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[ArtifactRecord]:
        """Execute image workflow and return artifact records

        Args:
            prompt: PromptRecord being processed
            json_data: Parsed ImagePromptData
            progress_callback: Optional callback for progress updates

        Returns:
            List of ArtifactRecord objects for generated images

        Raises:
            RuntimeError: If workflow execution fails
            subprocess.TimeoutExpired: If workflow times out
            FileNotFoundError: If workflow script not found
        """
        # Create output directory
        output_dir = self._create_output_directory(prompt.id, 'image')

        # Build command
        cmd = [
            self.python_executable,
            str(self.workflow_script),
            f'--{self.prompt_arg}', json_data.prompt,
            '--output', str(output_dir),
            '--comfyui-directory', str(self.comfyui_directory),
            '--queue-size', '1'
        ]

        if progress_callback:
            progress_callback(f"Starting image generation for prompt #{prompt.id}")

        # Execute subprocess
        try:
            print(f"\n🚀 EXECUTING IMAGE WORKFLOW - Prompt #{prompt.id}")
            print("-" * 80)
            print(f"Command: {' '.join(cmd)}")
            print(f"Working directory: {self.comfyui_directory}")
            print("-" * 80)

            result = subprocess.run(
                cmd,
                cwd=str(self.comfyui_directory),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )

            print(f"\n✅ IMAGE WORKFLOW COMPLETED - Prompt #{prompt.id}")
            print("-" * 80)
            print(f"Return code: {result.returncode}")

            if result.stdout:
                print(f"\n📤 STDOUT (length={len(result.stdout)} chars):")
                print("-" * 40)
                # Show last 2000 chars of stdout
                print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                print("-" * 40)

            if result.stderr:
                print(f"\n⚠️  STDERR (length={len(result.stderr)} chars):")
                print("-" * 40)
                # Show FULL stderr for debugging
                print(result.stderr)
                print("-" * 40)

            print("=" * 80)
            print()

            _write_generation_log(prompt.id, result)

            if result.returncode != 0:
                error_msg = f"Workflow failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nStderr: {result.stderr[-2000:]}"  # Show last 2000 chars
                if result.stdout:
                    error_msg += f"\nStdout: {result.stdout[-1000:]}"  # Also include some stdout
                raise RuntimeError(error_msg)

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Image workflow timed out after {self.timeout_seconds} seconds"
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Workflow script not found: {self.workflow_script}"
            )

        # Find generated PNG files
        artifacts = []
        png_files = list(output_dir.glob('*.png'))

        if not png_files:
            raise RuntimeError(
                f"No PNG files generated in {output_dir}. "
                f"Check ComfyUI output and workflow script."
            )

        for img_file in png_files:
            relative_path = self._get_relative_path(img_file)

            artifact = ArtifactRecord(
                id=None,  # Will be set by database
                prompt_id=prompt.id,
                artifact_type='image',
                file_path=relative_path,
                preview_path=relative_path,  # Same as file for images
                metadata={
                    'prompt': json_data.prompt,
                    'negative_prompt': json_data.negative_prompt,
                    'style_tags': json_data.style_tags,
                    'aspect_ratio': json_data.aspect_ratio,
                    'quality': json_data.quality,
                    'mood': json_data.mood,
                    'generated_at': datetime.now().isoformat(),
                    'file_size': img_file.stat().st_size,
                    'file_name': img_file.name
                }
            )
            artifacts.append(artifact)

        if progress_callback:
            progress_callback(f"Generated {len(artifacts)} image(s)")

        return artifacts


class AudioWorkflowExecutor(ComfyUIWorkflowExecutor):
    """Execute audio/song generation workflows"""

    def __init__(self, config: Dict[str, Any]):
        """Initialize audio workflow executor

        Args:
            config: Configuration dictionary
        """
        super().__init__(config)

        script_path = config['workflows']['song']['script']
        self.workflow_script = self.comfyui_directory / script_path
        self.prompt_arg = config['workflows']['song']['prompt_arg']

    def generate(
        self,
        prompt: PromptRecord,
        json_data: LyricsPromptData,
        progress_callback: Optional[Callable[[str], None]] = None,
        audio_params: Optional[Dict[str, Any]] = None
    ) -> List[ArtifactRecord]:
        """Execute audio workflow and return artifact records

        Args:
            prompt: PromptRecord being processed
            json_data: Parsed LyricsPromptData
            progress_callback: Optional callback for progress updates

        Returns:
            List of ArtifactRecord objects for generated audio files

        Raises:
            RuntimeError: If workflow execution fails
            subprocess.TimeoutExpired: If workflow times out
            FileNotFoundError: If workflow script not found
        """
        # Create output directory
        output_dir = self._create_output_directory(prompt.id, 'audio')

        # Get tags string (genre, mood, tempo, etc.)
        tags_text = json_data.get_tags_string()

        # Get full lyrics text with section markers
        lyrics_text = json_data.get_full_lyrics()

        # Log the formatted arguments for debugging
        print("=" * 80)
        print(f"AUDIO WORKFLOW ARGUMENTS - Prompt #{prompt.id}")
        print("=" * 80)
        print(f"\n📋 TAGS ARGUMENT (length={len(tags_text)} chars):")
        print("-" * 80)
        print(tags_text)
        print("-" * 80)
        print(f"\n🎵 LYRICS ARGUMENT (length={len(lyrics_text)} chars):")
        print("-" * 80)
        print(lyrics_text)
        print("-" * 80)

        # Build command for ACE audio workflow
        # Script expects --tags and --lyrics arguments
        cmd = [
            self.python_executable,
            str(self.workflow_script),
            '--tags', tags_text,
            '--lyrics', lyrics_text,
            '--output', str(output_dir),
            '--comfyui-directory', str(self.comfyui_directory),
            '--queue-size', '1'
        ]

        # Append optional ACE 1.5 generation parameters from GUI panel
        if audio_params:
            _param_flags = {
                'bpm':          '--bpm',
                'duration':     '--duration',
                'timesignature':'--timesignature',
                'keyscale':     '--keyscale',
                'language':     '--language',
                'cfg_scale':    '--cfg-scale',
                'temperature':  '--temperature',
                'top_p':        '--top-p',
                'top_k':        '--top-k',
                'min_p':        '--min-p',
            }
            for key, flag in _param_flags.items():
                if key in audio_params:
                    cmd.extend([flag, str(audio_params[key])])

        print(f"\n🚀 EXECUTING COMMAND:")
        print("-" * 80)
        # Print command in a readable format
        print(f"Python: {self.python_executable}")
        print(f"Script: {self.workflow_script}")
        print(f"--tags: {tags_text[:100]}{'...' if len(tags_text) > 100 else ''}")
        print(f"--lyrics: {lyrics_text[:100]}{'...' if len(lyrics_text) > 100 else ''}")
        print(f"--output: {output_dir}")
        print(f"--comfyui-directory: {self.comfyui_directory}")
        print(f"--queue-size: 1")
        if audio_params:
            print(f"Audio params overrides: {audio_params}")
        print("-" * 80)
        print()

        if progress_callback:
            progress_callback(f"Starting audio generation for prompt #{prompt.id}")

        # Execute subprocess
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.comfyui_directory),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )

            # Log subprocess output for debugging
            print(f"\n✅ WORKFLOW EXECUTION COMPLETED - Prompt #{prompt.id}")
            print("-" * 80)
            print(f"Return code: {result.returncode}")

            if result.stdout:
                print(f"\n📤 STDOUT (length={len(result.stdout)} chars):")
                print("-" * 40)
                # Show last 1000 chars of stdout
                print(result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout)
                print("-" * 40)

            if result.stderr:
                print(f"\n⚠️  STDERR (length={len(result.stderr)} chars):")
                print("-" * 40)
                # Show last 1000 chars of stderr
                print(result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr)
                print("-" * 40)

            print("=" * 80)
            print()

            _write_generation_log(prompt.id, result)

            if result.returncode != 0:
                error_msg = f"Workflow failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f"\nStderr: {result.stderr[-2000:]}"  # Show last 2000 chars
                raise RuntimeError(error_msg)

        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Audio workflow timed out after {self.timeout_seconds} seconds"
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Workflow script not found: {self.workflow_script}"
            )

        # Find generated MP3 files (could also be WAV, FLAC, etc.)
        artifacts = []
        audio_files = list(output_dir.glob('*.mp3'))
        audio_files.extend(output_dir.glob('*.wav'))
        audio_files.extend(output_dir.glob('*.flac'))

        if not audio_files:
            raise RuntimeError(
                f"No audio files generated in {output_dir}. "
                f"Check ComfyUI output and workflow script."
            )

        for audio_file in audio_files:
            relative_path = self._get_relative_path(audio_file)

            artifact = ArtifactRecord(
                id=None,  # Will be set by database
                prompt_id=prompt.id,
                artifact_type='audio',
                file_path=relative_path,
                preview_path=None,  # No preview for audio
                metadata={
                    'title': json_data.title,
                    'genre': json_data.genre,
                    'mood': json_data.mood,
                    'tempo': json_data.tempo,
                    'key': json_data.key,
                    'time_signature': json_data.time_signature,
                    'vocal_style': json_data.vocal_style,
                    'instrumentation': json_data.instrumentation,
                    'generated_at': datetime.now().isoformat(),
                    'file_size': audio_file.stat().st_size,
                    'file_name': audio_file.name,
                    'file_format': audio_file.suffix[1:]  # Remove leading dot
                }
            )
            artifacts.append(artifact)

        if progress_callback:
            progress_callback(f"Generated {len(artifacts)} audio file(s)")

        return artifacts
