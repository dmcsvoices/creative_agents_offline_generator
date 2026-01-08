#!/usr/bin/env python3
"""
Media Generator Application

Standalone tkinter GUI application that:
1. Queries pending prompts from SQLite database
2. Displays them in dual-list interface (Image | Song prompts)
3. Allows user selection and generation via ComfyUI workflows
4. Updates database with generated artifacts
5. Integrates with existing frontend for display

Usage:
    python media_generator_app.py
"""

import os
import sys
import json
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional

# Import local modules
from config import load_config, validate_config
from models import PromptRecord, ImagePromptData, LyricsPromptData
from repositories import PromptRepository, ArtifactRepository
from executors import ImageWorkflowExecutor, AudioWorkflowExecutor


class MediaGeneratorApp:
    """Main tkinter application window for media generation"""

    def __init__(self, config: dict):
        """Initialize application with configuration

        Args:
            config: Configuration dictionary
        """
        self.config = config

        # Initialize repositories
        db_path = config['database']['path']
        self.prompt_repo = PromptRepository(db_path)
        self.artifact_repo = ArtifactRepository(db_path)

        # State
        self.selected_image_prompt: Optional[PromptRecord] = None
        self.selected_lyrics_prompt: Optional[PromptRecord] = None

        # Create main window
        self.root = tk.Tk()
        self.root.title(config['ui']['window_title'])
        self.root.geometry(
            f"{config['ui']['window_width']}x{config['ui']['window_height']}"
        )

        # Build UI
        self.create_widgets()
        self.setup_menu_bar()

        # Initial load
        self.refresh_all_lists()

    def create_widgets(self):
        """Build all UI components"""

        # Main PanedWindow (vertical split: lists on top, details on bottom)
        main_paned = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        main_paned.pack(fill=tk.BOTH, expand=True)

        # === TOP FRAME: Horizontal split for dual lists ===
        top_frame = tk.Frame(main_paned)
        main_paned.add(top_frame, minsize=300)

        top_paned = tk.PanedWindow(top_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        top_paned.pack(fill=tk.BOTH, expand=True)

        # LEFT: Image Prompts List
        self._create_image_list_panel(top_paned)

        # RIGHT: Lyrics Prompts List
        self._create_lyrics_list_panel(top_paned)

        # === BOTTOM FRAME: Details panel ===
        self._create_details_panel(main_paned)

        # === CONTROL PANEL ===
        self._create_control_panel()

        # === STATUS BAR ===
        self._create_status_bar()

    def _create_image_list_panel(self, parent):
        """Create image prompts list panel

        Args:
            parent: Parent widget (PanedWindow)
        """
        image_frame = ttk.LabelFrame(parent, text="Image Prompts (Pending)")
        parent.add(image_frame, minsize=300)

        # Treeview
        self.image_tree = ttk.Treeview(
            image_frame,
            columns=('id', 'created', 'preview'),
            show='headings',
            selectmode='browse'
        )

        # Configure columns
        self.image_tree.heading('id', text='ID')
        self.image_tree.heading('created', text='Created')
        self.image_tree.heading('preview', text='Preview')

        self.image_tree.column('id', width=60, anchor='center')
        self.image_tree.column('created', width=140, anchor='w')
        self.image_tree.column('preview', width=300, anchor='w')

        # Scrollbar
        image_scroll = ttk.Scrollbar(image_frame, orient=tk.VERTICAL, command=self.image_tree.yview)
        self.image_tree.configure(yscrollcommand=image_scroll.set)

        # Pack
        self.image_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        image_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection event
        self.image_tree.bind('<<TreeviewSelect>>', self.on_image_select)

    def _create_lyrics_list_panel(self, parent):
        """Create lyrics prompts list panel

        Args:
            parent: Parent widget (PanedWindow)
        """
        lyrics_frame = ttk.LabelFrame(parent, text="Song Prompts (Pending)")
        parent.add(lyrics_frame, minsize=300)

        # Treeview
        self.lyrics_tree = ttk.Treeview(
            lyrics_frame,
            columns=('id', 'created', 'title'),
            show='headings',
            selectmode='browse'
        )

        # Configure columns
        self.lyrics_tree.heading('id', text='ID')
        self.lyrics_tree.heading('created', text='Created')
        self.lyrics_tree.heading('title', text='Title')

        self.lyrics_tree.column('id', width=60, anchor='center')
        self.lyrics_tree.column('created', width=140, anchor='w')
        self.lyrics_tree.column('title', width=300, anchor='w')

        # Scrollbar
        lyrics_scroll = ttk.Scrollbar(lyrics_frame, orient=tk.VERTICAL, command=self.lyrics_tree.yview)
        self.lyrics_tree.configure(yscrollcommand=lyrics_scroll.set)

        # Pack
        self.lyrics_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lyrics_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection event
        self.lyrics_tree.bind('<<TreeviewSelect>>', self.on_lyrics_select)

    def _create_details_panel(self, parent):
        """Create details panel for JSON display

        Args:
            parent: Parent widget (PanedWindow)
        """
        details_frame = ttk.LabelFrame(parent, text="Prompt Details (JSON)")
        parent.add(details_frame, minsize=200)

        self.details_text = scrolledtext.ScrolledText(
            details_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            height=10
        )
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _create_control_panel(self):
        """Create control button panel"""
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(
            control_frame,
            text="Generate Selected",
            command=self.generate_selected
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Refresh Lists",
            command=self.refresh_all_lists
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="View Output Folder",
            command=self.open_output_folder
        ).pack(side=tk.LEFT, padx=5)

    def _create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = tk.Label(
            self.root,
            text="Ready",
            relief=tk.SUNKEN,
            anchor=tk.W,
            bd=1
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def setup_menu_bar(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Refresh", command=self.refresh_all_lists, accelerator="Cmd+R")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Cmd+Q")

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(
            label="View Output Folder",
            command=self.open_output_folder,
            accelerator="Cmd+O"
        )

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        # Keyboard shortcuts
        self.root.bind('<Command-r>' if sys.platform == 'darwin' else '<Control-r>', lambda e: self.refresh_all_lists())
        self.root.bind('<Command-o>' if sys.platform == 'darwin' else '<Control-o>', lambda e: self.open_output_folder())
        self.root.bind('<Command-q>' if sys.platform == 'darwin' else '<Control-q>', lambda e: self.root.quit())

    def refresh_all_lists(self):
        """Reload both lists from database"""
        self.refresh_image_list()
        self.refresh_lyrics_list()
        self.update_status_bar()

    def refresh_image_list(self):
        """Query and populate image prompts list"""
        # Clear existing items
        self.image_tree.delete(*self.image_tree.get_children())

        try:
            prompts = self.prompt_repo.get_pending_image_prompts()

            for prompt in prompts:
                # Get preview from JSON
                json_data = prompt.get_json_prompt()
                prompt_text = json_data.get('prompt', '')
                preview = (prompt_text[:50] + '...') if len(prompt_text) > 50 else prompt_text

                # Insert into tree
                self.image_tree.insert('', 'end', iid=str(prompt.id), values=(
                    prompt.id,
                    prompt.created_at.strftime('%Y-%m-%d %H:%M'),
                    preview
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image prompts:\n{str(e)}")

    def refresh_lyrics_list(self):
        """Query and populate lyrics prompts list"""
        # Clear existing items
        self.lyrics_tree.delete(*self.lyrics_tree.get_children())

        try:
            prompts = self.prompt_repo.get_pending_lyrics_prompts()

            for prompt in prompts:
                # Get title from JSON
                json_data = prompt.get_json_prompt()
                title = json_data.get('title', 'Untitled')

                # Insert into tree
                self.lyrics_tree.insert('', 'end', iid=str(prompt.id), values=(
                    prompt.id,
                    prompt.created_at.strftime('%Y-%m-%d %H:%M'),
                    title
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load lyrics prompts:\n{str(e)}")

    def on_image_select(self, event):
        """Handle image prompt selection

        Args:
            event: Tkinter event
        """
        selection = self.image_tree.selection()
        if not selection:
            return

        prompt_id = int(selection[0])

        # Find prompt in cached list
        try:
            prompts = self.prompt_repo.get_pending_image_prompts()
            prompt = next((p for p in prompts if p.id == prompt_id), None)

            if prompt:
                self.selected_image_prompt = prompt
                self.selected_lyrics_prompt = None
                self.display_prompt_details(prompt)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load prompt details:\n{str(e)}")

    def on_lyrics_select(self, event):
        """Handle lyrics prompt selection

        Args:
            event: Tkinter event
        """
        selection = self.lyrics_tree.selection()
        if not selection:
            return

        prompt_id = int(selection[0])

        # Find prompt in cached list
        try:
            prompts = self.prompt_repo.get_pending_lyrics_prompts()
            prompt = next((p for p in prompts if p.id == prompt_id), None)

            if prompt:
                self.selected_lyrics_prompt = prompt
                self.selected_image_prompt = None
                self.display_prompt_details(prompt)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load prompt details:\n{str(e)}")

    def display_prompt_details(self, prompt: PromptRecord):
        """Show JSON details in text panel

        Args:
            prompt: PromptRecord to display
        """
        self.details_text.delete('1.0', tk.END)

        json_data = prompt.get_json_prompt()
        formatted_json = json.dumps(json_data, indent=2)

        self.details_text.insert('1.0', formatted_json)

    def generate_selected(self):
        """Generate media for selected prompt"""
        if self.selected_image_prompt:
            self.generate_image_prompt(self.selected_image_prompt)
        elif self.selected_lyrics_prompt:
            self.generate_lyrics_prompt(self.selected_lyrics_prompt)
        else:
            messagebox.showwarning(
                "No Selection",
                "Please select a prompt first by clicking on an item in either list."
            )

    def generate_image_prompt(self, prompt: PromptRecord):
        """Execute image generation workflow

        Args:
            prompt: PromptRecord to generate
        """
        try:
            # Update status to processing
            self.prompt_repo.update_artifact_status(prompt.id, 'processing')
            self.status_bar.config(text=f"Generating image for prompt #{prompt.id}...")
            self.root.update()

            # Parse JSON data
            json_data = ImagePromptData.from_json(prompt.get_json_prompt())

            # Execute workflow
            executor = ImageWorkflowExecutor(self.config)
            artifacts = executor.generate(
                prompt,
                json_data,
                progress_callback=self.update_status
            )

            # Save artifacts to database
            for artifact in artifacts:
                self.artifact_repo.save_artifact(artifact)

            # Update status to ready
            self.prompt_repo.update_artifact_status(prompt.id, 'ready')
            self.status_bar.config(
                text=f"Successfully generated {len(artifacts)} image(s)"
            )

            # Refresh list (prompt should disappear from pending)
            self.refresh_image_list()
            self.selected_image_prompt = None
            self.details_text.delete('1.0', tk.END)

            # Show success message
            messagebox.showinfo(
                "Success",
                f"Generated {len(artifacts)} image(s) for prompt #{prompt.id}\n\n"
                f"Files saved to output directory.\n"
                f"Frontend will display them automatically."
            )

        except Exception as e:
            error_msg = str(e)
            self.prompt_repo.update_artifact_status(prompt.id, 'error', error_msg)
            self.status_bar.config(text=f"Error: {error_msg[:100]}")
            messagebox.showerror("Generation Failed", error_msg)

    def generate_lyrics_prompt(self, prompt: PromptRecord):
        """Execute audio generation workflow

        Args:
            prompt: PromptRecord to generate
        """
        try:
            # Update status to processing
            self.prompt_repo.update_artifact_status(prompt.id, 'processing')
            self.status_bar.config(text=f"Generating audio for prompt #{prompt.id}...")
            self.root.update()

            # Parse JSON data
            json_data = LyricsPromptData.from_json(prompt.get_json_prompt())

            # Execute workflow
            executor = AudioWorkflowExecutor(self.config)
            artifacts = executor.generate(
                prompt,
                json_data,
                progress_callback=self.update_status
            )

            # Save artifacts to database
            for artifact in artifacts:
                self.artifact_repo.save_artifact(artifact)

            # Update status to ready
            self.prompt_repo.update_artifact_status(prompt.id, 'ready')
            self.status_bar.config(
                text=f"Successfully generated {len(artifacts)} audio file(s)"
            )

            # Refresh list (prompt should disappear from pending)
            self.refresh_lyrics_list()
            self.selected_lyrics_prompt = None
            self.details_text.delete('1.0', tk.END)

            # Show success message
            messagebox.showinfo(
                "Success",
                f"Generated {len(artifacts)} audio file(s) for prompt #{prompt.id}\n\n"
                f"Files saved to output directory.\n"
                f"Frontend will display them automatically."
            )

        except Exception as e:
            error_msg = str(e)
            self.prompt_repo.update_artifact_status(prompt.id, 'error', error_msg)
            self.status_bar.config(text=f"Error: {error_msg[:100]}")
            messagebox.showerror("Generation Failed", error_msg)

    def update_status(self, message: str):
        """Update status bar with message

        Args:
            message: Status message to display
        """
        self.status_bar.config(text=message)
        self.root.update()

    def update_status_bar(self):
        """Update status bar with prompt counts"""
        try:
            image_prompts = self.prompt_repo.get_pending_image_prompts()
            lyrics_prompts = self.prompt_repo.get_pending_lyrics_prompts()

            self.status_bar.config(
                text=f"Pending: {len(image_prompts)} images, {len(lyrics_prompts)} songs | Ready"
            )
        except Exception:
            self.status_bar.config(text="Ready")

    def open_output_folder(self):
        """Open output directory in file explorer"""
        output_dir = self.config['comfyui']['output_directory']

        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', output_dir], check=True)
            elif sys.platform == 'win32':  # Windows
                subprocess.run(['explorer', output_dir], check=True)
            else:  # Linux
                subprocess.run(['xdg-open', output_dir], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open output folder:\n{str(e)}")

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About Media Generator",
            "Media Generator Application\n"
            "Version 1.0\n\n"
            "Phase 2: Media Generation Interface\n"
            "Generates images and songs from pending prompts\n\n"
            f"Database: {self.config['database']['path']}\n"
            f"ComfyUI: {self.config['comfyui']['comfyui_directory']}\n\n"
            "Built with Python & Tkinter"
        )

    def run(self):
        """Start application main loop"""
        self.root.mainloop()


def main():
    """Application entry point"""
    # Determine config path
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'media_generator_config.json'
    )

    # Check config exists
    if not os.path.exists(config_path):
        print(f"ERROR: Configuration file not found: {config_path}")
        print()
        print("Please ensure media_generator_config.json exists in the same directory")
        print("as this script.")
        return 1

    # Load configuration
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        return 1

    # Validate configuration
    issues = validate_config(config)
    if issues:
        print("Configuration validation failed:")
        print()
        for issue in issues:
            print(f"  - {issue}")
        print()
        print("Please fix the configuration issues and try again.")
        return 1

    print("Configuration validated successfully")
    print(f"Database: {config['database']['path']}")
    print(f"ComfyUI: {config['comfyui']['comfyui_directory']}")
    print()
    print("Launching Media Generator Application...")
    print()

    # Launch application
    try:
        app = MediaGeneratorApp(config)
        app.run()
        return 0
    except Exception as e:
        print(f"ERROR: Application failed to start: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
