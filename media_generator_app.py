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
import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional

# Import local modules
from config import load_config, validate_config
from models import PromptRecord, ImagePromptData, LyricsPromptData
from repositories import PromptRepository, ArtifactRepository
from executors import ImageWorkflowExecutor, AudioWorkflowExecutor
from ui_components import ImageGallery, AudioPlayer


# Solarpunk Color Palette
COLORS = {
    'bg_primary': '#4A7C59',        # Deep Forest Green
    'bg_secondary': '#6B9B6E',      # Sage Green
    'bg_light': '#8FBC8F',          # Light Sage
    'bg_panel': '#F5F5DC',          # Beige White
    'text_primary': '#2F4F2F',      # Dark Forest
    'text_light': '#D4C5A9',        # Warm Sand
    'accent_solar': '#FFD93D',      # Bright Solar Yellow
    'accent_warm': '#F4A460',       # Warm Sunset Orange
    'border': '#8B7355',            # Rich Earth Brown
    'selected': '#B0C4DE',          # Light Steel Blue
    'hover': '#8FBC8F',             # Light Sage
    'status_ok': '#6B9B6E',         # Sage Green
    'status_error': '#CD5C5C',      # Indian Red (error state)
}


class GenerationTask:
    """Represents a single generation task"""
    def __init__(self, task_id, prompt_type, prompt, total_in_batch, position_in_batch):
        self.task_id = task_id
        self.prompt_type = prompt_type
        self.prompt = prompt
        self.total_in_batch = total_in_batch
        self.position_in_batch = position_in_batch


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
        self.selected_prompt: Optional[PromptRecord] = None
        self.selected_prompt_type: Optional[str] = None  # 'image_prompt' or 'lyrics_prompt'

        # Create main window
        self.root = tk.Tk()
        self.root.title(config['ui']['window_title'])
        self.root.geometry(
            f"{config['ui']['window_width']}x{config['ui']['window_height']}"
        )
        self.root.configure(bg=COLORS['border'])  # Border color shows as background

        # Create main container with border padding
        self.main_container = tk.Frame(
            self.root,
            bg=COLORS['bg_primary'],
            relief=tk.FLAT,
            bd=0
        )
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Threading components for non-blocking generation
        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.is_generating = False
        self.current_batch_total = 0
        self.current_batch_success = 0
        self.current_batch_errors = 0

        # Apply Solarpunk theme
        self.setup_styles()

        # Build UI
        self.create_widgets()
        self.setup_menu_bar()

        # Initial load
        self.refresh_unified_list()
        self.update_status_bar()

        # Start worker thread for background generation
        self._start_worker_thread()

    def setup_styles(self):
        """Configure ttk styles for Solarpunk theme"""
        style = ttk.Style()

        # Treeview styling
        style.configure(
            'Solarpunk.Treeview',
            background=COLORS['bg_panel'],
            foreground=COLORS['text_primary'],
            fieldbackground=COLORS['bg_panel'],
            borderwidth=0,
            font=('Helvetica Neue', 10)
        )

        style.configure(
            'Solarpunk.Treeview.Heading',
            background=COLORS['bg_secondary'],
            foreground=COLORS['text_light'],
            borderwidth=1,
            relief=tk.FLAT,
            font=('Helvetica Neue', 10, 'bold')
        )

        style.map(
            'Solarpunk.Treeview',
            background=[('selected', COLORS['selected'])],
            foreground=[('selected', COLORS['text_primary'])]
        )

        # Button styling
        style.configure(
            'Solarpunk.TButton',
            background=COLORS['accent_solar'],
            foreground=COLORS['text_primary'],
            borderwidth=0,
            focuscolor='none',
            font=('Helvetica Neue', 10, 'bold'),
            padding=(20, 10)
        )

        style.map(
            'Solarpunk.TButton',
            background=[
                ('active', COLORS['accent_warm']),
                ('pressed', COLORS['bg_secondary'])
            ],
            relief=[('pressed', tk.SUNKEN)]
        )

        # LabelFrame styling
        style.configure(
            'Solarpunk.TLabelframe',
            background=COLORS['bg_primary'],
            borderwidth=2,
            relief=tk.FLAT
        )

        style.configure(
            'Solarpunk.TLabelframe.Label',
            background=COLORS['bg_primary'],
            foreground=COLORS['text_light'],
            font=('Helvetica Neue', 11, 'bold')
        )

        # Scrollbar styling (limited on some platforms)
        style.configure(
            'Solarpunk.Vertical.TScrollbar',
            background=COLORS['bg_secondary'],
            troughcolor=COLORS['bg_light'],
            borderwidth=0,
            arrowcolor=COLORS['text_primary']
        )

        # Notebook (tabs) styling
        style.configure(
            'Solarpunk.TNotebook',
            background=COLORS['bg_primary'],
            borderwidth=0
        )

        style.configure(
            'Solarpunk.TNotebook.Tab',
            background=COLORS['bg_secondary'],
            foreground=COLORS['text_light'],
            padding=(20, 10),
            font=('Helvetica Neue', 11, 'bold')
        )

        style.map(
            'Solarpunk.TNotebook.Tab',
            background=[
                ('selected', COLORS['accent_solar']),
                ('active', COLORS['bg_light'])
            ],
            foreground=[
                ('selected', COLORS['text_primary']),
                ('active', COLORS['text_primary'])
            ]
        )

        # Combobox styling (for filter dropdown)
        style.configure(
            'Solarpunk.TCombobox',
            fieldbackground=COLORS['bg_panel'],
            background=COLORS['bg_secondary'],
            foreground=COLORS['text_primary'],
            arrowcolor=COLORS['text_primary'],
            borderwidth=1
        )

    def create_widgets(self):
        """Build all UI components"""

        # === ENHANCED STATUS DISPLAY (TOP) ===
        self._create_status_display()

        # === MAIN TABS NOTEBOOK ===
        self.main_notebook = ttk.Notebook(
            self.main_container,
            style='Solarpunk.TNotebook'
        )
        self.main_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Tab 1: Prompts & Generation
        self._create_prompts_tab()

        # Tab 2: Image Gallery
        self._create_image_gallery_tab()

        # Tab 3: Audio Gallery
        self._create_audio_gallery_tab()

    def _create_status_display(self):
        """Create enhanced status display at top of window"""
        # Status container frame
        status_container = tk.Frame(
            self.main_container,
            bg=COLORS['bg_secondary'],
            height=60
        )
        status_container.pack(fill=tk.X, side=tk.TOP, pady=(0, 5))
        status_container.pack_propagate(False)

        # Status icon (left side)
        self.status_icon_label = tk.Label(
            status_container,
            text="✓",  # Unicode checkmark
            font=('Helvetica Neue', 24),
            bg=COLORS['bg_secondary'],
            fg=COLORS['status_ok'],
            width=2
        )
        self.status_icon_label.pack(side=tk.LEFT, padx=10)

        # Status message (center)
        self.status_message_label = tk.Label(
            status_container,
            text="Ready",
            font=('Helvetica Neue', 14, 'bold'),
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_light'],
            anchor=tk.W
        )
        self.status_message_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Progress bar (right side, initially hidden)
        self.status_progress = ttk.Progressbar(
            status_container,
            mode='indeterminate',
            length=200
        )
        # Pack only when needed

    def _create_prompts_tab(self):
        """Create Tab 1: Prompts & Generation"""
        tab1 = tk.Frame(self.main_notebook, bg=COLORS['bg_panel'])
        self.main_notebook.add(tab1, text="⚙ Prompts")

        # Vertical PanedWindow (resizable split)
        tab1_paned = tk.PanedWindow(
            tab1,
            orient=tk.VERTICAL,
            sashrelief=tk.FLAT,
            bg=COLORS['bg_primary'],
            sashwidth=4,
            bd=0
        )
        tab1_paned.pack(fill=tk.BOTH, expand=True)

        # TOP: Prompts section
        prompts_section = self._create_prompts_section(tab1_paned)
        tab1_paned.add(prompts_section, minsize=200)

        # BOTTOM: JSON viewer
        json_section = self._create_json_section(tab1_paned)
        tab1_paned.add(json_section, minsize=100)

        # FIXED BOTTOM: Generate button
        self._create_generate_button(tab1)

    def _create_prompts_section(self, parent):
        """Create prompts list with filter"""
        prompts_container = tk.Frame(parent, bg=COLORS['bg_primary'])

        # Filter frame at top
        filter_frame = tk.Frame(
            prompts_container,
            bg=COLORS['bg_secondary'],
            height=40
        )
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        filter_frame.pack_propagate(False)

        # Filter label
        filter_label = tk.Label(
            filter_frame,
            text="Show:",
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_light'],
            font=('Helvetica Neue', 11, 'bold')
        )
        filter_label.pack(side=tk.LEFT, padx=(10, 5))

        # Filter dropdown
        self.filter_var = tk.StringVar(value="All")
        self.filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.filter_var,
            values=["All", "Images", "Audio"],
            state='readonly',
            width=12,
            style='Solarpunk.TCombobox'
        )
        self.filter_combo.pack(side=tk.LEFT, padx=5)
        self.filter_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_unified_list())

        # Refresh button
        tk.Button(
            filter_frame,
            text="Refresh",
            command=self.refresh_unified_list,
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_light'],
            font=('Helvetica Neue', 10),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=15,
            pady=5,
            cursor='hand2'
        ).pack(side=tk.RIGHT, padx=10)

        # Prompts list frame
        prompts_frame = ttk.LabelFrame(
            prompts_container,
            text="Pending Prompts",
            style='Solarpunk.TLabelframe'
        )
        prompts_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Unified Treeview with EXTENDED selectmode for multi-select
        self.unified_tree = ttk.Treeview(
            prompts_frame,
            columns=('icon', 'type', 'id', 'created', 'preview'),
            show='headings',
            selectmode='extended',  # Changed from 'browse' to 'extended'
            style='Solarpunk.Treeview'
        )

        # Configure columns
        self.unified_tree.heading('icon', text='')
        self.unified_tree.heading('type', text='Type')
        self.unified_tree.heading('id', text='ID')
        self.unified_tree.heading('created', text='Created')
        self.unified_tree.heading('preview', text='Preview')

        self.unified_tree.column('icon', width=40, anchor='center')
        self.unified_tree.column('type', width=80, anchor='w')
        self.unified_tree.column('id', width=60, anchor='center')
        self.unified_tree.column('created', width=140, anchor='w')
        self.unified_tree.column('preview', width=400, anchor='w')

        # Scrollbar
        unified_scroll = ttk.Scrollbar(
            prompts_frame,
            orient=tk.VERTICAL,
            command=self.unified_tree.yview,
            style='Solarpunk.Vertical.TScrollbar'
        )
        self.unified_tree.configure(yscrollcommand=unified_scroll.set)

        # Pack
        self.unified_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        unified_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection event
        self.unified_tree.bind('<<TreeviewSelect>>', self.on_unified_select)

        return prompts_container

    def _create_json_section(self, parent):
        """Create JSON viewer section"""
        json_frame = ttk.LabelFrame(
            parent,
            text="Prompt Details (JSON)",
            style='Solarpunk.TLabelframe'
        )

        # ScrolledText for JSON display
        self.details_text = scrolledtext.ScrolledText(
            json_frame,
            wrap=tk.WORD,
            font=('Consolas', 11),
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            insertbackground=COLORS['accent_solar'],
            selectbackground=COLORS['selected'],
            selectforeground=COLORS['text_primary'],
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10,
            height=10
        )
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        return json_frame

    def _create_generate_button(self, parent):
        """Create generate button at bottom of prompts tab"""
        button_frame = tk.Frame(parent, bg=COLORS['bg_secondary'], height=50)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        button_frame.pack_propagate(False)

        self.generate_button = tk.Button(
            button_frame,
            text="Generate Selected",
            command=self.generate_selected,
            bg=COLORS['accent_solar'],
            fg=COLORS['text_primary'],
            font=('Helvetica Neue', 12, 'bold'),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=30,
            pady=12,
            cursor='hand2'
        )
        self.generate_button.pack(expand=True)

    def _create_image_gallery_tab(self):
        """Create Tab 2: Image Gallery"""
        tab2 = tk.Frame(self.main_notebook, bg=COLORS['bg_panel'])
        self.main_notebook.add(tab2, text="📷 Images")

        # Create ImageGallery widget (will be redesigned in ui_components.py)
        output_dir = self.config['comfyui']['output_directory']
        self.image_gallery = ImageGallery(tab2, output_dir)
        self.image_gallery.frame.pack(fill=tk.BOTH, expand=True)

        # Load images
        self.image_gallery.load_images()

    def _create_audio_gallery_tab(self):
        """Create Tab 3: Audio Gallery"""
        tab3 = tk.Frame(self.main_notebook, bg=COLORS['bg_panel'])
        self.main_notebook.add(tab3, text="🎵 Audio")

        # Create AudioPlayer widget with database access for metadata
        output_dir = self.config['comfyui']['output_directory']
        self.audio_player = AudioPlayer(tab3, output_dir, self.prompt_repo)
        self.audio_player.frame.pack(fill=tk.BOTH, expand=True)

        # Load playlist
        self.audio_player.load_playlist()


    def setup_menu_bar(self):
        """Create menu bar"""
        menubar = tk.Menu(
            self.root,
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_light'],
            activebackground=COLORS['accent_solar'],
            activeforeground=COLORS['text_primary'],
            borderwidth=0
        )
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(
            menubar,
            tearoff=0,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['accent_solar'],
            activeforeground=COLORS['text_primary']
        )
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Refresh", command=self.refresh_unified_list, accelerator="Cmd+R")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Cmd+Q")

        # Tools menu
        tools_menu = tk.Menu(
            menubar,
            tearoff=0,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['accent_solar'],
            activeforeground=COLORS['text_primary']
        )
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(
            label="View Output Folder",
            command=self.open_output_folder,
            accelerator="Cmd+O"
        )

        # Help menu
        help_menu = tk.Menu(
            menubar,
            tearoff=0,
            bg=COLORS['bg_panel'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['accent_solar'],
            activeforeground=COLORS['text_primary']
        )
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        # Keyboard shortcuts
        self.root.bind('<Command-r>' if sys.platform == 'darwin' else '<Control-r>', lambda e: self.refresh_unified_list())
        self.root.bind('<Command-o>' if sys.platform == 'darwin' else '<Control-o>', lambda e: self.open_output_folder())
        self.root.bind('<Command-q>' if sys.platform == 'darwin' else '<Control-q>', lambda e: self.root.quit())

    # Icon map for prompt types
    ICON_MAP = {
        'image_prompt': '🖼️',  # Frame with picture
        'lyrics_prompt': '🎵',  # Musical note
    }

    def refresh_unified_list(self):
        """Reload unified prompts list from database"""
        # Clear existing items
        self.unified_tree.delete(*self.unified_tree.get_children())

        try:
            # Get filter value
            filter_value = self.filter_var.get()

            # Load both prompt types
            image_prompts = self.prompt_repo.get_pending_image_prompts() if filter_value in ["All", "Images"] else []
            lyrics_prompts = self.prompt_repo.get_pending_lyrics_prompts() if filter_value in ["All", "Audio"] else []

            # Combine into unified list with type info
            all_prompts = []
            for prompt in image_prompts:
                all_prompts.append(('image_prompt', prompt))
            for prompt in lyrics_prompts:
                all_prompts.append(('lyrics_prompt', prompt))

            # Sort by timestamp (newest first)
            all_prompts.sort(key=lambda x: x[1].created_at, reverse=True)

            # Insert into tree
            for prompt_type, prompt in all_prompts:
                # Get icon and type label
                icon = self.ICON_MAP[prompt_type]
                type_label = 'Image' if prompt_type == 'image_prompt' else 'Audio'

                # Get preview text
                json_data = prompt.get_json_prompt()
                if prompt_type == 'image_prompt':
                    prompt_text = json_data.get('prompt', '')
                    preview = (prompt_text[:50] + '...') if len(prompt_text) > 50 else prompt_text
                else:
                    title = json_data.get('title', 'Untitled')
                    preview = title

                # Insert into tree
                self.unified_tree.insert('', 'end', iid=f"{prompt_type}_{prompt.id}", values=(
                    icon,
                    type_label,
                    prompt.id,
                    prompt.created_at.strftime('%Y-%m-%d %H:%M'),
                    preview
                ))

            # Update status bar
            self.update_status_bar()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load prompts:\n{str(e)}")

    def on_unified_select(self, event):
        """Handle prompt selection from unified list (supports multi-select)

        Args:
            event: Tkinter event
        """
        selections = self.unified_tree.selection()

        # Update button label based on selection count
        count = len(selections)
        if count == 0:
            self.generate_button.config(text="Generate Selected", state=tk.DISABLED)
            self.selected_prompt = None
            self.selected_prompt_type = None
            return
        elif count == 1:
            self.generate_button.config(text="Generate Selected", state=tk.NORMAL)
        else:
            self.generate_button.config(text=f"Generate Selected ({count} prompts)", state=tk.NORMAL)

        # Display JSON of the most recently selected prompt
        item_id = selections[-1] if selections else None
        if not item_id:
            return

        # Parse item ID (format: "prompt_type_id")
        parts = item_id.split('_')
        if len(parts) < 2:
            return

        prompt_type = '_'.join(parts[:-1])  # Handle 'image_prompt' vs 'lyrics_prompt'
        prompt_id = int(parts[-1])

        # Find prompt in appropriate list
        try:
            if prompt_type == 'image_prompt':
                prompts = self.prompt_repo.get_pending_image_prompts()
            else:
                prompts = self.prompt_repo.get_pending_lyrics_prompts()

            prompt = next((p for p in prompts if p.id == prompt_id), None)

            if prompt:
                self.selected_prompt = prompt
                self.selected_prompt_type = prompt_type
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
        """Queue selected prompts for background generation"""
        selections = self.unified_tree.selection()

        if not selections:
            messagebox.showwarning("No Selection", "Please select one or more prompts.")
            return

        # Prevent multiple simultaneous batches
        if self.is_generating:
            messagebox.showinfo("Generation In Progress", "Please wait for current generation to complete.")
            return

        # Parse all selected prompts
        prompts_to_generate = []
        for item_id in selections:
            parts = item_id.split('_')
            if len(parts) < 2:
                continue

            prompt_type = '_'.join(parts[:-1])
            prompt_id = int(parts[-1])

            try:
                if prompt_type == 'image_prompt':
                    prompts = self.prompt_repo.get_pending_image_prompts()
                else:
                    prompts = self.prompt_repo.get_pending_lyrics_prompts()

                prompt = next((p for p in prompts if p.id == prompt_id), None)
                if prompt:
                    prompts_to_generate.append((prompt_type, prompt))
            except Exception as e:
                print(f"Failed to load prompt {prompt_id}: {e}")
                continue

        if not prompts_to_generate:
            messagebox.showwarning("Error", "Failed to load selected prompts")
            return

        # Initialize batch tracking
        self.is_generating = True
        self.current_batch_total = len(prompts_to_generate)
        self.current_batch_success = 0
        self.current_batch_errors = 0

        # Queue all tasks
        for idx, (prompt_type, prompt) in enumerate(prompts_to_generate, 1):
            task = GenerationTask(
                task_id=idx,
                prompt_type=prompt_type,
                prompt=prompt,
                total_in_batch=len(prompts_to_generate),
                position_in_batch=idx
            )
            self.task_queue.put(task)

        # Update UI immediately
        self.update_status(f"Queued {len(prompts_to_generate)} prompt(s) for generation...", 'processing')
        self.generate_button.config(state=tk.DISABLED)

    def _start_worker_thread(self):
        """Start background worker thread for generation"""
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="GenerationWorker"
        )
        self.worker_thread.start()

    def _worker_loop(self):
        """Worker thread main loop - processes tasks from queue"""
        while True:
            try:
                # Block until task available
                task = self.task_queue.get(block=True)

                # Schedule UI update on main thread
                self.root.after(0, self._update_generation_status,
                              task.position_in_batch, task.total_in_batch,
                              task.prompt_type, task.prompt.id)

                try:
                    # Perform generation (blocking subprocess is OK here)
                    if task.prompt_type == 'image_prompt':
                        self._generate_image_prompt_silent(task.prompt)
                    elif task.prompt_type == 'lyrics_prompt':
                        self._generate_lyrics_prompt_silent(task.prompt)

                    # Success - schedule UI update
                    self.root.after(0, self._on_task_success, task)

                except Exception as e:
                    # Error - schedule UI update
                    self.root.after(0, self._on_task_error, task, str(e))

                finally:
                    self.task_queue.task_done()

            except Exception as e:
                print(f"Worker thread error: {e}")
                import traceback
                traceback.print_exc()

    def _update_generation_status(self, current, total, prompt_type, prompt_id):
        """Update status bar (called on main thread)"""
        type_label = 'Image' if prompt_type == 'image_prompt' else 'Audio'
        self.update_status(
            f"Generating {current}/{total}: {type_label} prompt #{prompt_id}...",
            'processing'
        )
        self.generate_button.config(state=tk.DISABLED)

    def _on_task_success(self, task):
        """Handle successful task (called on main thread)"""
        self.current_batch_success += 1

        if (self.current_batch_success + self.current_batch_errors) >= self.current_batch_total:
            self._on_batch_complete()

    def _on_task_error(self, task, error_msg):
        """Handle task error (called on main thread)"""
        self.current_batch_errors += 1
        print(f"Generation error for prompt #{task.prompt.id}: {error_msg}")

        try:
            self.prompt_repo.update_artifact_status(task.prompt.id, 'error', error_msg[:500])
        except Exception as e:
            print(f"Failed to update error status: {e}")

        if (self.current_batch_success + self.current_batch_errors) >= self.current_batch_total:
            self._on_batch_complete()

    def _on_batch_complete(self):
        """Handle batch completion (called on main thread)"""
        self.is_generating = False

        # Refresh UI
        self.refresh_unified_list()
        self.image_gallery.load_images()
        self.audio_player.load_playlist()

        # Re-enable button
        self.generate_button.config(state=tk.NORMAL)

        # Show results
        if self.current_batch_errors == 0:
            self.update_status(
                f"Successfully generated {self.current_batch_success} prompt(s)",
                'success'
            )
            messagebox.showinfo(
                "Success",
                f"Successfully generated {self.current_batch_success} prompt(s)!"
            )
        else:
            self.update_status(
                f"Completed: {self.current_batch_success} successful, {self.current_batch_errors} failed",
                'error' if self.current_batch_success == 0 else 'success'
            )
            messagebox.showwarning(
                "Partial Success",
                f"Generated {self.current_batch_success} prompt(s).\n"
                f"{self.current_batch_errors} failed."
            )

        # Reset counters
        self.current_batch_total = 0
        self.current_batch_success = 0
        self.current_batch_errors = 0

    def _generate_image_prompt_silent(self, prompt: PromptRecord):
        """Execute image generation workflow (silent, no dialogs)

        Args:
            prompt: PromptRecord to generate
        """
        # Update status to processing
        self.prompt_repo.update_artifact_status(prompt.id, 'processing')

        # Parse JSON data
        json_data = ImagePromptData.from_json(prompt.get_json_prompt())

        # Execute workflow
        executor = ImageWorkflowExecutor(self.config)
        artifacts = executor.generate(
            prompt,
            json_data,
            progress_callback=lambda msg: None  # Silent
        )

        # Save artifacts to database
        for artifact in artifacts:
            self.artifact_repo.save_artifact(artifact)

        # Update status to ready
        self.prompt_repo.update_artifact_status(prompt.id, 'ready')

    def generate_image_prompt(self, prompt: PromptRecord):
        """Execute image generation workflow (with user feedback)

        Args:
            prompt: PromptRecord to generate
        """
        try:
            self.update_status(f"Generating image for prompt #{prompt.id}...", 'processing')
            self.root.update()

            # Use silent method
            self._generate_image_prompt_silent(prompt)

            self.update_status(f"Successfully generated image(s)", 'success')

            # Refresh list and gallery
            self.refresh_unified_list()
            self.image_gallery.load_images()

            # Switch to Images tab
            self.main_notebook.select(1)  # Tab index 1 = Images

            # Show success message
            messagebox.showinfo(
                "Success",
                f"Generated image(s) for prompt #{prompt.id}\n\n"
                f"View them in the Images tab!"
            )

        except Exception as e:
            error_msg = str(e)
            self.prompt_repo.update_artifact_status(prompt.id, 'error', error_msg)
            self.update_status(f"Error: {error_msg[:100]}", 'error')
            messagebox.showerror("Generation Failed", error_msg)

    def _generate_lyrics_prompt_silent(self, prompt: PromptRecord):
        """Execute audio generation workflow (silent, no dialogs)

        Args:
            prompt: PromptRecord to generate
        """
        # Update status to processing
        self.prompt_repo.update_artifact_status(prompt.id, 'processing')

        # Parse JSON data
        json_data = LyricsPromptData.from_json(prompt.get_json_prompt())

        # Execute workflow
        executor = AudioWorkflowExecutor(self.config)
        artifacts = executor.generate(
            prompt,
            json_data,
            progress_callback=lambda msg: None  # Silent
        )

        # Save artifacts to database
        for artifact in artifacts:
            self.artifact_repo.save_artifact(artifact)

        # Update status to ready
        self.prompt_repo.update_artifact_status(prompt.id, 'ready')

    def generate_lyrics_prompt(self, prompt: PromptRecord):
        """Execute audio generation workflow (with user feedback)

        Args:
            prompt: PromptRecord to generate
        """
        try:
            self.update_status(f"Generating audio for prompt #{prompt.id}...", 'processing')
            self.root.update()

            # Use silent method
            self._generate_lyrics_prompt_silent(prompt)

            self.update_status(f"Successfully generated audio file(s)", 'success')

            # Refresh list and player
            self.refresh_unified_list()
            self.audio_player.load_playlist()

            # Switch to Audio tab
            self.main_notebook.select(2)  # Tab index 2 = Audio

            # Show success message
            messagebox.showinfo(
                "Success",
                f"Generated audio file(s) for prompt #{prompt.id}\n\n"
                f"Listen to them in the Audio tab!"
            )

        except Exception as e:
            error_msg = str(e)
            self.prompt_repo.update_artifact_status(prompt.id, 'error', error_msg)
            self.update_status(f"Error: {error_msg[:100]}", 'error')
            messagebox.showerror("Generation Failed", error_msg)

    def update_status(self, message: str, state: str = 'ready'):
        """Update status display with message and state

        Args:
            message: Status message to display
            state: Status state ('ready', 'processing', 'success', 'error')
        """
        # Update message
        self.status_message_label.config(text=message)

        # Update icon and color based on state
        if state == 'processing':
            self.status_icon_label.config(text="⟳", fg=COLORS['accent_solar'])
            # Show progress bar
            if not self.status_progress.winfo_ismapped():
                self.status_progress.pack(side=tk.RIGHT, padx=10)
                self.status_progress.start(10)
        elif state == 'success':
            self.status_icon_label.config(text="✓", fg=COLORS['status_ok'])
            # Hide progress bar
            if self.status_progress.winfo_ismapped():
                self.status_progress.stop()
                self.status_progress.pack_forget()
        elif state == 'error':
            self.status_icon_label.config(text="✗", fg=COLORS['status_error'])
            # Hide progress bar
            if self.status_progress.winfo_ismapped():
                self.status_progress.stop()
                self.status_progress.pack_forget()
        else:  # ready
            self.status_icon_label.config(text="✓", fg=COLORS['status_ok'])
            # Hide progress bar
            if self.status_progress.winfo_ismapped():
                self.status_progress.stop()
                self.status_progress.pack_forget()

        self.root.update()

    def update_status_bar(self):
        """Update status display with prompt counts"""
        try:
            image_prompts = self.prompt_repo.get_pending_image_prompts()
            lyrics_prompts = self.prompt_repo.get_pending_lyrics_prompts()

            total = len(image_prompts) + len(lyrics_prompts)
            if total > 0:
                self.update_status(
                    f"Ready - {len(image_prompts)} image prompts, {len(lyrics_prompts)} audio prompts pending",
                    'ready'
                )
            else:
                self.update_status("Ready - No pending prompts", 'ready')
        except Exception:
            self.update_status("Ready", 'ready')

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
