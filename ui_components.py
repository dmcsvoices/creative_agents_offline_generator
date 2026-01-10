"""
Custom UI components for Media Generator App
Contains ImageGallery and AudioPlayer widgets
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import subprocess
import sys

# Solarpunk color palette (imported from main app)
COLORS = {
    'bg_primary': '#4A7C59',    # Deep Forest Green
    'bg_secondary': '#6B9B6E',  # Sage Green
    'bg_light': '#8FB98E',      # Lighter sage
    'bg_panel': '#F5F5DC',      # Beige White
    'text_primary': '#2F4F2F',  # Dark Forest
    'text_light': '#D4C5A9',    # Warm Sand
    'accent_solar': '#FFD93D',  # Bright Solar Yellow
    'accent_warm': '#F4A460',   # Warm Sunset Orange
    'selected': '#B0C4DE',      # Light Steel Blue
    'error': '#CD5C5C',         # Indian Red
}


class ImageGallery:
    """Image gallery with file list and single full-size image viewer"""

    def __init__(self, parent, output_dir):
        self.output_dir = output_dir
        self.image_files = []
        self.current_photo = None
        self.current_image_path = None

        # Main frame (horizontal split)
        self.frame = tk.Frame(parent, bg=COLORS['bg_panel'])

        # === LEFT: File List (~10% width) ===
        file_list_frame = tk.Frame(self.frame, bg=COLORS['bg_panel'], width=100)
        file_list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0), pady=5)
        file_list_frame.pack_propagate(False)

        # File list label
        list_label = tk.Label(
            file_list_frame,
            text="Files",
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=('Helvetica Neue', 10, 'bold')
        )
        list_label.pack(side=tk.TOP, pady=(0, 5))

        # Listbox for files
        self.file_listbox = tk.Listbox(
            file_list_frame,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=('Consolas', 9),
            selectbackground=COLORS['selected'],
            selectmode='browse',
            highlightthickness=0,
            bd=0
        )
        self.file_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Horizontal scrollbar for long filenames
        h_scroll = ttk.Scrollbar(
            file_list_frame,
            orient=tk.HORIZONTAL,
            command=self.file_listbox.xview
        )
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.file_listbox.configure(xscrollcommand=h_scroll.set)

        # Bind selection
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)

        # === RIGHT: Image Display (>90% width) ===
        self.image_canvas = tk.Canvas(
            self.frame,
            bg='#1a1a1a',
            highlightthickness=0,
            bd=0
        )
        self.image_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bind resize to redraw image
        self.image_canvas.bind('<Configure>', self._on_canvas_resize)

        # Bind double-click to open in system viewer
        self.image_canvas.bind('<Double-Button-1>', self._on_double_click)

    def _on_canvas_resize(self, event):
        """Redraw image when canvas is resized"""
        if self.current_image_path:
            # Defer redraw slightly to avoid excessive redraws during resize
            self.image_canvas.after(100, lambda: self.display_image(self.current_image_path))

    def _on_double_click(self, event):
        """Open current image in system viewer on double-click"""
        if self.current_image_path:
            self._view_full_image(self.current_image_path)

    def load_images(self):
        """Load image list from output directory"""
        # Clear existing
        self.file_listbox.delete(0, tk.END)
        self.image_files.clear()
        self.current_photo = None
        self.current_image_path = None

        # Find all image files in output_dir/image/
        image_dir = Path(self.output_dir) / 'image'
        if not image_dir.exists():
            self._show_no_images_message()
            return

        image_files = []
        for subdir in image_dir.iterdir():
            if subdir.is_dir():
                image_files.extend(subdir.glob('*.png'))
                image_files.extend(subdir.glob('*.jpg'))
                image_files.extend(subdir.glob('*.jpeg'))

        if not image_files:
            self._show_no_images_message()
            return

        # Sort by modification time (newest first)
        image_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Store files and populate listbox
        self.image_files = image_files
        for img_path in image_files:
            # Extract prompt number from parent directory name
            # Path structure: output_dir/image/{prompt_id}_{timestamp}/output.png
            # Example: 219_20260109T150634
            dir_name = img_path.parent.name

            # Extract just the prompt ID (before the first underscore)
            prompt_id = dir_name.split('_')[0] if '_' in dir_name else dir_name

            display_text = f"Prompt #{prompt_id}"
            self.file_listbox.insert(tk.END, display_text)

        # Auto-select first image
        if self.image_files:
            self.file_listbox.selection_set(0)
            self.on_file_select(None)

    def on_file_select(self, event):
        """Handle file selection from listbox"""
        selection = self.file_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self.image_files):
            return

        image_path = self.image_files[idx]
        self.display_image(image_path)

    def display_image(self, image_path):
        """Display single image scaled to fit canvas while maintaining aspect ratio"""
        try:
            from PIL import Image, ImageTk

            # Load original image
            img = Image.open(image_path)

            # Convert to RGB if needed (handle PNG transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode in ('RGBA', 'LA'):
                    background.paste(img, mask=img.split()[-1])
                    img = background

            # Get canvas dimensions
            self.image_canvas.update_idletasks()
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()

            # Fallback dimensions if canvas not yet rendered
            if canvas_width <= 1:
                canvas_width = 800
            if canvas_height <= 1:
                canvas_height = 600

            # Calculate scaling to fit canvas (maintain aspect ratio)
            img_ratio = img.width / img.height
            canvas_ratio = canvas_width / canvas_height

            if img_ratio > canvas_ratio:
                # Image is wider than canvas - width-constrained
                new_width = canvas_width - 20  # Padding
                new_height = int(new_width / img_ratio)
            else:
                # Image is taller than canvas - height-constrained
                new_height = canvas_height - 20  # Padding
                new_width = int(new_height * img_ratio)

            # Resize image
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(img_resized)

            # Center on canvas
            x = (canvas_width - new_width) // 2
            y = (canvas_height - new_height) // 2

            # Clear and draw
            self.image_canvas.delete('all')
            self.image_canvas.create_image(x, y, anchor='nw', image=self.current_photo)

            # Store current path for resize and double-click
            self.current_image_path = image_path

        except Exception as e:
            print(f"Failed to display image {image_path}: {e}")
            self._show_error_message(str(e))

    def _view_full_image(self, image_path):
        """Open image in system viewer"""
        try:
            if sys.platform == 'darwin':
                subprocess.run(['open', str(image_path)])
            elif sys.platform == 'win32':
                subprocess.run(['start', str(image_path)], shell=True)
            else:
                subprocess.run(['xdg-open', str(image_path)])
        except Exception as e:
            print(f"Failed to open image: {e}")

    def _show_no_images_message(self):
        """Display message when no images found"""
        self.file_listbox.insert(tk.END, "(no images yet)")
        self.image_canvas.delete('all')
        self.image_canvas.create_text(
            400, 300,
            text="No generated images yet.\nGenerate some prompts to see them here!",
            fill=COLORS['text_primary'],
            font=('Helvetica Neue', 14),
            justify=tk.CENTER
        )

    def _show_error_message(self, error_msg):
        """Display error message on canvas"""
        self.image_canvas.delete('all')
        self.image_canvas.create_text(
            400, 300,
            text=f"Failed to load image\n{error_msg}",
            fill=COLORS['error'],
            font=('Helvetica Neue', 12),
            justify=tk.CENTER
        )


class AudioPlayer:
    """Audio player with file list and playback controls"""

    def __init__(self, parent, output_dir, prompt_repo=None):
        self.output_dir = output_dir
        self.prompt_repo = prompt_repo
        self.current_file = None
        self.is_playing = False
        self.audio_files = []
        self.audio_backend = None
        self.audio_duration_ms = 0

        # Main container (horizontal split)
        self.frame = tk.Frame(parent, bg=COLORS['bg_panel'])

        # === LEFT: File List (wider for more info) ===
        file_list_frame = tk.Frame(self.frame, bg=COLORS['bg_panel'], width=450)
        file_list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0), pady=5)
        file_list_frame.pack_propagate(False)

        # File list label
        list_label = tk.Label(
            file_list_frame,
            text="Audio Files",
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=('Helvetica Neue', 10, 'bold')
        )
        list_label.pack(side=tk.TOP, pady=(0, 5))

        # Treeview for structured display
        self.playlist = ttk.Treeview(
            file_list_frame,
            columns=('prompt', 'filename', 'title'),
            show='headings',
            selectmode='browse',
            style='Solarpunk.Treeview'
        )

        # Configure columns
        self.playlist.heading('prompt', text='Prompt #')
        self.playlist.heading('filename', text='Filename')
        self.playlist.heading('title', text='Song Title')

        self.playlist.column('prompt', width=70, minwidth=70, anchor='center')
        self.playlist.column('filename', width=120, minwidth=100)
        self.playlist.column('title', width=240, minwidth=150)

        self.playlist.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Scrollbars
        v_scroll = ttk.Scrollbar(file_list_frame, orient=tk.VERTICAL, command=self.playlist.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.playlist.configure(yscrollcommand=v_scroll.set)

        # Bind selection
        self.playlist.bind('<<TreeviewSelect>>', self.on_file_select)

        # === RIGHT: Controls (>90% width) ===
        right_frame = tk.Frame(self.frame, bg=COLORS['bg_panel'])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Controls at bottom
        controls_frame = tk.Frame(right_frame, bg=COLORS['bg_panel'])
        controls_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        # Play/Pause button
        self.play_button = tk.Button(
            controls_frame,
            text="▶ Play",
            command=self.toggle_playback,
            bg=COLORS['accent_solar'],
            fg=COLORS['text_primary'],
            font=('Helvetica Neue', 11, 'bold'),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=20,
            pady=8,
            cursor='hand2'
        )
        self.play_button.pack(side=tk.LEFT, padx=5)

        # Stop button
        self.stop_button = tk.Button(
            controls_frame,
            text="■ Stop",
            command=self.stop_playback,
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_light'],
            font=('Helvetica Neue', 11),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=20,
            pady=8,
            cursor='hand2'
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Time label
        self.time_label = tk.Label(
            controls_frame,
            text="0:00 / 0:00",
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            font=('Consolas', 11)
        )
        self.time_label.pack(side=tk.RIGHT, padx=10)

        # Initialize audio backend
        self._init_audio_backend()

    def _init_audio_backend(self):
        """Initialize audio playback backend"""
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.audio_backend = 'pygame'
        except ImportError:
            # Fallback: use system command
            self.audio_backend = 'system'
            print("pygame not available, using system command for audio playback")

    def load_playlist(self):
        """Load audio files from output directory with metadata"""
        # Clear existing
        for item in self.playlist.get_children():
            self.playlist.delete(item)
        self.audio_files.clear()

        audio_dir = Path(self.output_dir) / 'audio'
        if not audio_dir.exists():
            return

        audio_files = []
        for subdir in audio_dir.iterdir():
            if subdir.is_dir():
                audio_files.extend(subdir.glob('*.wav'))
                audio_files.extend(subdir.glob('*.mp3'))
                audio_files.extend(subdir.glob('*.flac'))

        if not audio_files:
            return

        # Sort by modification time (newest first)
        audio_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Store files and populate treeview
        self.audio_files = audio_files
        for audio_file in audio_files:
            # Extract prompt number from parent directory name
            # Path structure: output_dir/audio/{prompt_id}_{timestamp}/output.wav
            # Example: 219_20260109T150634
            dir_name = audio_file.parent.name
            filename = audio_file.name

            # Extract just the prompt ID (before the first underscore)
            prompt_id = dir_name.split('_')[0] if '_' in dir_name else dir_name

            # Fetch song title from database
            song_title = "(Unknown)"
            if self.prompt_repo:
                try:
                    import json

                    # Query directly from database by ID
                    try:
                        prompt_id_int = int(prompt_id)

                        # Query via prompts table to get the writing content
                        with self.prompt_repo.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(
                                """SELECT w.content
                                   FROM prompts p
                                   INNER JOIN writings w ON p.output_reference = w.id
                                   WHERE p.id = ?""",
                                (prompt_id_int,)
                            )
                            result = cursor.fetchone()

                            if result:
                                # Parse JSON and extract title directly
                                json_data = json.loads(result[0])
                                song_title = json_data.get('title', '(No title)')
                                print(f"Found song title for prompt {prompt_id}: {song_title}")
                            else:
                                print(f"No database record found for prompt {prompt_id}")
                    except (ValueError, json.JSONDecodeError) as e:
                        print(f"Failed to parse prompt {prompt_id}: {e}")
                        import traceback
                        traceback.print_exc()
                except Exception as e:
                    print(f"Failed to fetch song title for prompt {prompt_id}: {e}")
                    import traceback
                    traceback.print_exc()

            # Insert into treeview
            self.playlist.insert('', 'end', values=(f"#{prompt_id}", filename, song_title))

    def on_file_select(self, event):
        """Handle file selection from playlist (Treeview)"""
        selection = self.playlist.selection()
        if not selection:
            return

        # Get the selected item
        item_id = selection[0]
        item_index = self.playlist.index(item_id)

        if item_index >= len(self.audio_files):
            return

        # Stop current playback
        if self.is_playing:
            self.stop_playback()

        self.current_file = self.audio_files[item_index]
        # No waveform loading - just set current file for playback

    def toggle_playback(self):
        """Play or pause audio"""
        if not self.current_file:
            return

        if self.audio_backend == 'pygame':
            import pygame

            if self.is_playing:
                pygame.mixer.music.pause()
                self.play_button.config(text="▶ Play")
                self.is_playing = False
            else:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.unpause()
                else:
                    pygame.mixer.music.load(str(self.current_file))
                    pygame.mixer.music.play()
                self.play_button.config(text="⏸ Pause")
                self.is_playing = True
                self._start_playback_update()
        else:
            # System command fallback
            try:
                if sys.platform == 'darwin':
                    subprocess.Popen(['afplay', str(self.current_file)])
                elif sys.platform == 'win32':
                    subprocess.Popen(['start', str(self.current_file)], shell=True)
                else:
                    subprocess.Popen(['xdg-open', str(self.current_file)])
                self.is_playing = True
                self.play_button.config(text="⏸ Playing")
            except Exception as e:
                print(f"Failed to play audio: {e}")

    def stop_playback(self):
        """Stop audio playback"""
        if self.audio_backend == 'pygame':
            import pygame
            pygame.mixer.music.stop()

        self.is_playing = False
        self.play_button.config(text="▶ Play")
        self.time_label.config(text="0:00 / 0:00")

    def _start_playback_update(self):
        """Update playback position display"""
        if not self.is_playing:
            return

        if self.audio_backend == 'pygame':
            import pygame

            # Get current position
            if pygame.mixer.music.get_busy():
                pos_ms = pygame.mixer.music.get_pos()

                # Update time label
                current_time = pos_ms / 1000.0
                total_time = self.audio_duration_ms / 1000.0
                self.time_label.config(
                    text=f"{self._format_time(current_time)} / {self._format_time(total_time)}"
                )

                # Schedule next update
                self.frame.after(50, self._start_playback_update)
            else:
                # Playback finished
                self.is_playing = False
                self.play_button.config(text="▶ Play")

    def _format_time(self, seconds):
        """Format seconds as M:SS"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}:{secs:02d}"
