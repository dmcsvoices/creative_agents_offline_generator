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
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional

# Import local modules
from config import load_config, validate_config
from models import PromptRecord, ImagePromptData, LyricsPromptData, ArtifactRecord
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


class SplashScreen:
    """Splash screen with solarpunk theme that displays for 5 seconds"""

    def __init__(self, parent):
        self.splash = tk.Toplevel(parent)
        self.splash.overrideredirect(True)  # Remove window decorations

        # Set window size
        window_width = 600
        window_height = 400

        # Center the splash screen on the screen
        screen_width = self.splash.winfo_screenwidth()
        screen_height = self.splash.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)

        self.splash.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        self.splash.configure(bg=COLORS['bg_primary'])

        # Create main frame
        main_frame = tk.Frame(self.splash, bg=COLORS['bg_primary'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(
            main_frame,
            text="MEDIA GENERATOR",
            font=('Helvetica Neue', 32, 'bold'),
            fg=COLORS['accent_solar'],
            bg=COLORS['bg_primary']
        )
        title_label.pack(pady=(30, 10))

        subtitle_label = tk.Label(
            main_frame,
            text="Solarpunk Edition",
            font=('Helvetica Neue', 18),
            fg=COLORS['text_light'],
            bg=COLORS['bg_primary']
        )
        subtitle_label.pack(pady=(0, 30))

        # Animated elements
        self.canvas = tk.Canvas(
            main_frame,
            width=300,
            height=150,
            bg=COLORS['bg_primary'],
            highlightthickness=0
        )
        self.canvas.pack(pady=20)

        # Draw solarpunk elements
        self.draw_solarpunk_elements()

        # Loading text
        self.loading_label = tk.Label(
            main_frame,
            text="Initializing...",
            font=('Helvetica Neue', 14),
            fg=COLORS['text_light'],
            bg=COLORS['bg_primary']
        )
        self.loading_label.pack(pady=10)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            maximum=100,
            length=300,
            mode='determinate'
        )
        progress_bar.pack(pady=10)

        # Version info
        version_label = tk.Label(
            main_frame,
            text="v1.0.0",
            font=('Helvetica Neue', 10),
            fg=COLORS['text_light'],
            bg=COLORS['bg_primary']
        )
        version_label.pack(pady=(30, 0))

        # Start animation
        self.animation_step = 0
        self.animate_elements()

        # Start progress simulation
        self.progress_step = 0
        self.update_progress()

        # Close splash after 10 seconds
        self.splash.after(10000, self.close_splash)

    def draw_solarpunk_elements(self):
        """Draw solarpunk-themed elements on canvas"""
        # Draw sun-like circle
        self.canvas.create_oval(100, 30, 200, 130,
                               fill=COLORS['accent_solar'],
                               outline=COLORS['accent_warm'],
                               width=2)

        # Draw leaves/organic shapes
        self.canvas.create_arc(50, 50, 100, 100,
                              start=30, extent=120,
                              style=tk.ARC,
                              outline=COLORS['bg_light'],
                              width=3)

        self.canvas.create_arc(200, 50, 250, 100,
                              start=150, extent=120,
                              style=tk.ARC,
                              outline=COLORS['bg_light'],
                              width=3)

        # Draw organic patterns
        self.canvas.create_line(80, 100, 120, 80,
                               fill=COLORS['bg_light'],
                               width=2)

        self.canvas.create_line(180, 80, 220, 100,
                               fill=COLORS['bg_light'],
                               width=2)

        # Draw small circles representing nodes
        self.canvas.create_oval(70, 70, 80, 80,
                               fill=COLORS['accent_warm'],
                               outline=COLORS['bg_primary'])

        self.canvas.create_oval(220, 70, 230, 80,
                               fill=COLORS['accent_warm'],
                               outline=COLORS['bg_primary'])

    def animate_elements(self):
        """Animate elements on the splash screen"""
        # Simple animation to rotate or pulse elements
        self.animation_step += 1

        # Clear canvas and redraw with slight variations
        self.canvas.delete("all")
        self.draw_solarpunk_elements()

        # Add pulsing effect to sun
        pulse_offset = abs(5 - (self.animation_step % 10))
        # Calculate hex value for dynamic solar yellow
        green_val = min(255, 0x3D + pulse_offset)
        sun_fill = f'#FFD9{green_val:02X}'  # Dynamic solar yellow

        # Redraw sun with pulsing effect
        self.canvas.create_oval(100, 30, 200, 130,
                               fill=sun_fill,
                               outline=COLORS['accent_warm'],
                               width=2)

        # Schedule next animation frame
        self.splash.after(100, self.animate_elements)

    def update_progress(self):
        """Simulate progress update"""
        self.progress_step += 1
        progress_percent = min(100, self.progress_step)  # Will reach 100% in 10 seconds (updating every 100ms for 100 steps)
        self.progress_var.set(progress_percent)

        # Update loading text periodically
        if self.progress_step % 20 == 0:  # Update every 2 seconds (20 * 100ms = 2000ms)
            texts = [
                "Initializing...",
                "Loading resources...",
                "Preparing interface...",
                "Building connections...",
                "Almost ready...",
                "Starting application..."
            ]
            current_text = texts[(self.progress_step // 20) % len(texts)]
            self.loading_label.config(text=current_text)

        if self.progress_step < 100:  # Continue updating for 10 seconds
            self.splash.after(100, self.update_progress)

    def close_splash(self):
        """Close the splash screen"""
        self.splash.destroy()

    def wait_for_close(self):
        """Wait for the splash screen to close"""
        while self.splash.winfo_exists():
            self.splash.update_idletasks()
            self.splash.update()
            time.sleep(0.01)


class GenerationTask:
    """Represents a single generation task"""
    def __init__(self, task_id, prompt_type, prompt, total_in_batch, position_in_batch,
                 audio_params=None, is_regen=False):
        self.task_id = task_id
        self.prompt_type = prompt_type
        self.prompt = prompt
        self.total_in_batch = total_in_batch
        self.position_in_batch = position_in_batch
        self.audio_params = audio_params  # Optional dict of ACE 1.5 generation params
        self.is_regen = is_regen          # If True: run executor but skip all DB writes
        self.regen_artifacts = []         # Populated by worker on successful regen


class MediaGeneratorApp:
    """Main tkinter application window for media generation"""

    def __init__(self, config: dict, root: Optional[tk.Tk] = None):
        """Initialize application with configuration

        Args:
            config: Configuration dictionary
            root: Optional existing Tk root window. If None, creates a new one.
        """
        self.config = config

        # Initialize repositories
        db_path = config['database']['path']
        self.prompt_repo = PromptRepository(db_path)
        self.artifact_repo = ArtifactRepository(db_path)

        # Reset any stale processing prompts from previous crashes
        stale_count = self.prompt_repo.reset_stale_processing_prompts(timeout_minutes=30)
        if stale_count > 0:
            print(f"✓ Reset {stale_count} stale prompts from previous session")

        # State
        self.selected_prompt: Optional[PromptRecord] = None
        self.selected_prompt_type: Optional[str] = None  # 'image_prompt' or 'lyrics_prompt'

        # History tab state
        self.history_selected_prompt: Optional[PromptRecord] = None
        self.history_selected_type: Optional[str] = None
        self.history_last_regen_artifacts: list = []   # ArtifactRecords from last regen (not in DB)

        # Create or use existing main window
        self.root = root if root is not None else tk.Tk()
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

        # Tab 4: History & Regeneration
        self._create_history_tab()

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

        # FIXED BOTTOM: Generate button — must be packed BEFORE the expanding
        # PanedWindow so tkinter reserves its space first.
        self._create_generate_button(tab1)

        # Vertical PanedWindow (resizable split) — fills remaining space
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

        # BOTTOM: JSON / Audio Params notebook
        json_section = self._create_json_section(tab1_paned)
        tab1_paned.add(json_section, minsize=100)

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

        # Clear button (remove from display only)
        tk.Button(
            filter_frame,
            text="Clear",
            command=self.clear_selected,
            bg=COLORS['bg_secondary'],
            fg=COLORS['text_light'],
            font=('Helvetica Neue', 10),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=15,
            pady=5,
            cursor='hand2'
        ).pack(side=tk.RIGHT, padx=5)

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
        """Create details section: JSON viewer + Audio Params as notebook tabs."""
        # Wrapper frame that sits inside the PanedWindow pane
        section_frame = tk.Frame(parent, bg=COLORS['bg_primary'])

        self.details_notebook = ttk.Notebook(section_frame, style='Solarpunk.TNotebook')
        self.details_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── Tab 0: JSON viewer ───────────────────────────────────────────────
        json_tab = tk.Frame(self.details_notebook, bg=COLORS['bg_panel'])
        self.details_notebook.add(json_tab, text="  Details (JSON)  ")

        self.details_text = scrolledtext.ScrolledText(
            json_tab,
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
        )
        self.details_text.pack(fill=tk.BOTH, expand=True)

        # ── Tab 1: Audio generation parameters ──────────────────────────────
        audio_tab = tk.Frame(self.details_notebook, bg=COLORS['bg_primary'])
        self.details_notebook.add(audio_tab, text="  Audio Params (ACE 1.5)  ")
        self._build_audio_params_panel(audio_tab)

        return section_frame

    def _create_generate_button(self, parent):
        """Create generate button at bottom of prompts tab."""
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

    # ── Audio params defaults ──────────────────────────────────────────────────
    _AUDIO_DEFAULTS = {
        'bpm': 190, 'duration': 120, 'keyscale': 'E minor',
        'timesignature': '4', 'language': 'en', 'cfg_scale': 2.0,
        'temperature': 0.85, 'top_p': 0.9, 'top_k': 0, 'min_p': 0.0,
    }
    _KEY_SCALE_OPTIONS = [
        'C major', 'D major', 'E major', 'F major', 'G major', 'A major', 'B major',
        'C minor', 'D minor', 'E minor', 'F minor', 'G minor', 'A minor', 'B minor',
        'C# major', 'Eb major', 'F# major', 'Ab major', 'Bb major',
        'C# minor', 'Eb minor', 'F# minor', 'Ab minor', 'Bb minor',
    ]

    def _build_audio_params_panel(self, parent):
        """Build the Audio Generation Parameters widget grid into the given parent frame."""
        inner = tk.Frame(parent, bg=COLORS['bg_primary'])
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        # ── tk variables (read back in _get_audio_params) ──────────────────
        d = self._AUDIO_DEFAULTS
        self._ap_bpm          = tk.IntVar(value=d['bpm'])
        self._ap_duration     = tk.IntVar(value=d['duration'])
        self._ap_keyscale     = tk.StringVar(value=d['keyscale'])
        self._ap_timesig      = tk.StringVar(value=d['timesignature'])
        self._ap_language     = tk.StringVar(value=d['language'])
        self._ap_cfg_scale    = tk.DoubleVar(value=d['cfg_scale'])
        self._ap_temperature  = tk.DoubleVar(value=d['temperature'])
        self._ap_top_p        = tk.DoubleVar(value=d['top_p'])
        self._ap_top_k        = tk.IntVar(value=d['top_k'])
        self._ap_min_p        = tk.DoubleVar(value=d['min_p'])

        # ── shared widget styles ───────────────────────────────────────────
        lbl_kw = dict(bg=COLORS['bg_primary'], fg=COLORS['text_light'],
                      font=('Helvetica Neue', 10), anchor='e')
        spinbox_kw = dict(bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                          relief=tk.FLAT, highlightthickness=1,
                          highlightbackground=COLORS['border'],
                          font=('Helvetica Neue', 10), width=7)
        combo_kw = dict(style='Solarpunk.TCombobox', state='normal')

        def lbl(row, col, text):
            tk.Label(inner, text=text, **lbl_kw).grid(
                row=row, column=col, sticky='e', padx=(10, 4), pady=4)

        def spinbox(row, col, var, lo, hi, inc=1, fmt=None):
            kw = dict(textvariable=var, from_=lo, to=hi, increment=inc, **spinbox_kw)
            if fmt:
                kw['format'] = fmt
            tk.Spinbox(inner, **kw).grid(row=row, column=col, sticky='w', padx=(0, 8))

        # ── Row 0: BPM | Duration ──────────────────────────────────────────
        lbl(0, 0, 'BPM:')
        spinbox(0, 1, self._ap_bpm, 40, 320)

        lbl(0, 2, 'Duration (s):')
        spinbox(0, 3, self._ap_duration, 15, 300)

        # ── Row 1: Key/Scale | Time Signature ─────────────────────────────
        lbl(1, 0, 'Key / Scale:')
        ttk.Combobox(inner, textvariable=self._ap_keyscale, width=14,
                     values=self._KEY_SCALE_OPTIONS, **combo_kw).grid(
            row=1, column=1, sticky='w', padx=(0, 8), pady=4)

        lbl(1, 2, 'Time Signature:')
        ttk.Combobox(inner, textvariable=self._ap_timesig, width=5,
                     values=['3', '4', '6', '12'], state='readonly',
                     style='Solarpunk.TCombobox').grid(
            row=1, column=3, sticky='w', padx=(0, 8), pady=4)

        # ── Row 2: CFG Scale | Language ───────────────────────────────────
        lbl(2, 0, 'CFG Scale:')
        spinbox(2, 1, self._ap_cfg_scale, 0.5, 15.0, inc=0.5, fmt='%4.1f')

        lbl(2, 2, 'Language:')
        ttk.Combobox(inner, textvariable=self._ap_language, width=5,
                     values=['en', 'zh', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'ru'],
                     state='readonly', style='Solarpunk.TCombobox').grid(
            row=2, column=3, sticky='w', padx=(0, 8), pady=4)

        # ── Row 3: Temperature | Top P ────────────────────────────────────
        lbl(3, 0, 'Temperature:')
        spinbox(3, 1, self._ap_temperature, 0.05, 2.0, inc=0.05, fmt='%4.2f')

        lbl(3, 2, 'Top P:')
        spinbox(3, 3, self._ap_top_p, 0.0, 1.0, inc=0.05, fmt='%4.2f')

        # ── Row 4: Top K | Min P ──────────────────────────────────────────
        lbl(4, 0, 'Top K:')
        spinbox(4, 1, self._ap_top_k, 0, 500)

        lbl(4, 2, 'Min P:')
        spinbox(4, 3, self._ap_min_p, 0.0, 1.0, inc=0.05, fmt='%4.2f')

        # ── Row 5: Reset button ───────────────────────────────────────────
        tk.Button(
            inner, text='Reset Defaults',
            command=self._reset_audio_params,
            bg=COLORS['bg_secondary'], fg=COLORS['text_light'],
            font=('Helvetica Neue', 9), relief=tk.FLAT,
            bd=0, highlightthickness=0, padx=12, pady=3, cursor='hand2'
        ).grid(row=5, column=0, columnspan=4, pady=(6, 2))

        # Grid column weights: labels narrow, widgets wider
        inner.columnconfigure(0, weight=0, minsize=110)
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(2, weight=0, minsize=120)
        inner.columnconfigure(3, weight=1)

    def _show_audio_params_panel(self):
        """Switch details notebook to the Audio Params tab."""
        self.details_notebook.select(1)

    def _hide_audio_params_panel(self):
        """Switch details notebook to the JSON tab."""
        self.details_notebook.select(0)

    def _build_audio_params_widgets_only(self, parent):
        """Build audio param widgets into *parent* using the already-existing self._ap_* vars.

        Call this after _build_audio_params_panel() has already created the variables
        (i.e. after _create_prompts_tab() has run).  Produces an identical grid so
        both the Prompts tab and the History tab share the same underlying values.
        """
        inner = tk.Frame(parent, bg=COLORS['bg_primary'])
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        lbl_kw = dict(bg=COLORS['bg_primary'], fg=COLORS['text_light'],
                      font=('Helvetica Neue', 10), anchor='e')
        spinbox_kw = dict(bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
                          relief=tk.FLAT, highlightthickness=1,
                          highlightbackground=COLORS['border'],
                          font=('Helvetica Neue', 10), width=7)
        combo_kw = dict(style='Solarpunk.TCombobox', state='normal')

        def lbl(row, col, text):
            tk.Label(inner, text=text, **lbl_kw).grid(
                row=row, column=col, sticky='e', padx=(10, 4), pady=4)

        def spinbox(row, col, var, lo, hi, inc=1, fmt=None):
            kw = dict(textvariable=var, from_=lo, to=hi, increment=inc, **spinbox_kw)
            if fmt:
                kw['format'] = fmt
            tk.Spinbox(inner, **kw).grid(row=row, column=col, sticky='w', padx=(0, 8))

        lbl(0, 0, 'BPM:');       spinbox(0, 1, self._ap_bpm, 40, 320)
        lbl(0, 2, 'Duration (s):'); spinbox(0, 3, self._ap_duration, 15, 300)

        lbl(1, 0, 'Key / Scale:')
        ttk.Combobox(inner, textvariable=self._ap_keyscale, width=14,
                     values=self._KEY_SCALE_OPTIONS, **combo_kw).grid(
            row=1, column=1, sticky='w', padx=(0, 8), pady=4)

        lbl(1, 2, 'Time Signature:')
        ttk.Combobox(inner, textvariable=self._ap_timesig, width=5,
                     values=['3', '4', '6', '12'], state='readonly',
                     style='Solarpunk.TCombobox').grid(
            row=1, column=3, sticky='w', padx=(0, 8), pady=4)

        lbl(2, 0, 'CFG Scale:');  spinbox(2, 1, self._ap_cfg_scale, 0.5, 15.0, inc=0.5, fmt='%4.1f')
        lbl(2, 2, 'Language:')
        ttk.Combobox(inner, textvariable=self._ap_language, width=5,
                     values=['en', 'zh', 'ja', 'ko', 'fr', 'de', 'es', 'pt', 'ru'],
                     state='readonly', style='Solarpunk.TCombobox').grid(
            row=2, column=3, sticky='w', padx=(0, 8), pady=4)

        lbl(3, 0, 'Temperature:'); spinbox(3, 1, self._ap_temperature, 0.05, 2.0, inc=0.05, fmt='%4.2f')
        lbl(3, 2, 'Top P:');       spinbox(3, 3, self._ap_top_p, 0.0, 1.0, inc=0.05, fmt='%4.2f')
        lbl(4, 0, 'Top K:');       spinbox(4, 1, self._ap_top_k, 0, 500)
        lbl(4, 2, 'Min P:');       spinbox(4, 3, self._ap_min_p, 0.0, 1.0, inc=0.05, fmt='%4.2f')

        tk.Button(
            inner, text='Reset Defaults',
            command=self._reset_audio_params,
            bg=COLORS['bg_secondary'], fg=COLORS['text_light'],
            font=('Helvetica Neue', 9), relief=tk.FLAT,
            bd=0, highlightthickness=0, padx=12, pady=3, cursor='hand2',
        ).grid(row=5, column=0, columnspan=4, pady=(6, 2))

        inner.columnconfigure(0, weight=0, minsize=110)
        inner.columnconfigure(1, weight=1)
        inner.columnconfigure(2, weight=0, minsize=120)
        inner.columnconfigure(3, weight=1)

    def _reset_audio_params(self):
        """Restore all audio param widgets to their factory defaults."""
        d = self._AUDIO_DEFAULTS
        self._ap_bpm.set(d['bpm'])
        self._ap_duration.set(d['duration'])
        self._ap_keyscale.set(d['keyscale'])
        self._ap_timesig.set(d['timesignature'])
        self._ap_language.set(d['language'])
        self._ap_cfg_scale.set(d['cfg_scale'])
        self._ap_temperature.set(d['temperature'])
        self._ap_top_p.set(d['top_p'])
        self._ap_top_k.set(d['top_k'])
        self._ap_min_p.set(d['min_p'])

    def _populate_audio_params_from_prompt(self, json_data: dict):
        """Pre-fill audio params from the selected prompt's metadata where available."""
        meta = json_data.get('metadata', {})

        # Key → keyscale
        key = meta.get('key', '')
        if key:
            self._ap_keyscale.set(key)

        # Time signature → extract numerator (e.g. "4/4" → "4", "3/4" → "3")
        time_sig = meta.get('time_signature', '')
        if time_sig:
            numerator = time_sig.split('/')[0].strip()
            if numerator in ('3', '4', '6', '12'):
                self._ap_timesig.set(numerator)

    def _get_audio_params(self) -> dict:
        """Read current audio param widget values and return as a dict."""
        return {
            'bpm':          self._ap_bpm.get(),
            'duration':     self._ap_duration.get(),
            'keyscale':     self._ap_keyscale.get(),
            'timesignature':self._ap_timesig.get(),
            'language':     self._ap_language.get(),
            'cfg_scale':    round(self._ap_cfg_scale.get(), 2),
            'temperature':  round(self._ap_temperature.get(), 2),
            'top_p':        round(self._ap_top_p.get(), 2),
            'top_k':        self._ap_top_k.get(),
            'min_p':        round(self._ap_min_p.get(), 2),
        }

    def _create_image_gallery_tab(self):
        """Create Tab 2: Image Gallery"""
        tab2 = tk.Frame(self.main_notebook, bg=COLORS['bg_panel'])
        self.main_notebook.add(tab2, text="📷 Images")

        output_dir = self.config['comfyui']['output_directory']
        self.image_gallery = ImageGallery(
            tab2, output_dir,
            on_export=self._export_file,
            on_promote=lambda p: self._promote_file(p, 'image'),
        )
        self.image_gallery.frame.pack(fill=tk.BOTH, expand=True)
        self.image_gallery.load_images()

    def _create_audio_gallery_tab(self):
        """Create Tab 3: Audio Gallery"""
        tab3 = tk.Frame(self.main_notebook, bg=COLORS['bg_panel'])
        self.main_notebook.add(tab3, text="🎵 Audio")

        output_dir = self.config['comfyui']['output_directory']
        self.audio_player = AudioPlayer(
            tab3, output_dir, self.prompt_repo,
            on_export=self._export_file,
            on_promote=lambda p: self._promote_file(p, 'audio'),
        )
        self.audio_player.frame.pack(fill=tk.BOTH, expand=True)
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
        file_menu.add_command(label="Force Checkpoint & Refresh", command=self.force_database_checkpoint, accelerator="Cmd+Shift+R")
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

    def force_database_checkpoint(self):
        """Force WAL checkpoint to see latest data from poets service"""
        try:
            from db_utils import force_wal_checkpoint
            db_path = self.config['database']['path']

            print(f"Forcing WAL checkpoint...")
            if force_wal_checkpoint(db_path, mode="TRUNCATE"):
                print("✓ WAL checkpoint successful")
                messagebox.showinfo("Success", "Database checkpoint completed.\nNow refreshing prompts...")
                self.refresh_unified_list()
            else:
                print("⚠️ WAL checkpoint failed (database may be busy)")
                messagebox.showwarning("Warning", "Checkpoint partially completed.\nTrying refresh anyway...")
                self.refresh_unified_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to checkpoint: {e}")

    def refresh_unified_list(self):
        """Reload unified prompts list from database"""
        # Clear existing items
        self.unified_tree.delete(*self.unified_tree.get_children())

        try:
            # Get filter value
            filter_value = self.filter_var.get()

            print("\n" + "=" * 80)
            print(f"REFRESHING PROMPTS LIST (filter={filter_value})")
            print("=" * 80)

            # Load both prompt types
            print(f"[DEBUG] Querying for pending prompts...")
            image_prompts = self.prompt_repo.get_pending_image_prompts() if filter_value in ["All", "Images"] else []
            lyrics_prompts = self.prompt_repo.get_pending_lyrics_prompts() if filter_value in ["All", "Audio"] else []
            print(f"[DEBUG] Query results: {len(image_prompts)} image prompts, {len(lyrics_prompts)} lyrics prompts")
            print("=" * 80 + "\n")

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
            self._hide_audio_params_panel()
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

                # Show/hide audio params panel and populate from prompt data
                if prompt_type == 'lyrics_prompt':
                    self._populate_audio_params_from_prompt(prompt.get_json_prompt())
                    self._show_audio_params_panel()
                else:
                    self._hide_audio_params_panel()
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

    def clear_selected(self):
        """Remove selected prompts from display (does not affect database)

        The prompts remain in the database and will reappear when Refresh is clicked.
        """
        selections = self.unified_tree.selection()

        if not selections:
            messagebox.showinfo("No Selection", "Please select one or more prompts to clear from the display.")
            return

        # Confirm action
        count = len(selections)
        response = messagebox.askyesno(
            "Clear from Display",
            f"Remove {count} prompt(s) from the display?\n\n"
            "The prompts will remain in the database and can be restored by clicking Refresh."
        )

        if response:
            # Remove items from tree
            for item_id in selections:
                self.unified_tree.delete(item_id)

            # Clear selection state
            self.selected_prompt = None
            self.selected_prompt_type = None
            self.details_text.delete('1.0', tk.END)

            # Update status
            self.update_status(f"Cleared {count} prompt(s) from display", 'ready')
            self.update_status_bar()

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

        # Snapshot audio params once for the whole batch (captured at queue time)
        batch_audio_params = self._get_audio_params()

        # Queue all tasks
        for idx, (prompt_type, prompt) in enumerate(prompts_to_generate, 1):
            task = GenerationTask(
                task_id=idx,
                prompt_type=prompt_type,
                prompt=prompt,
                total_in_batch=len(prompts_to_generate),
                position_in_batch=idx,
                audio_params=batch_audio_params if prompt_type == 'lyrics_prompt' else None
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
                    if task.is_regen:
                        # Sandbox regen: run executor only, no DB writes
                        if task.prompt_type == 'image_prompt':
                            task.regen_artifacts = self._regen_image_silent(task.prompt)
                        elif task.prompt_type == 'lyrics_prompt':
                            task.regen_artifacts = self._regen_lyrics_silent(
                                task.prompt, audio_params=task.audio_params)
                    else:
                        if task.prompt_type == 'image_prompt':
                            self._generate_image_prompt_silent(task.prompt)
                        elif task.prompt_type == 'lyrics_prompt':
                            self._generate_lyrics_prompt_silent(task.prompt, audio_params=task.audio_params)

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

        if task.is_regen:
            # Sandbox regen: special completion handler, then release generating lock
            self.is_generating = False
            self.generate_button.config(state=tk.NORMAL)
            self.current_batch_total = 0
            self.current_batch_success = 0
            self.current_batch_errors = 0
            self._on_regen_complete(task)
            return

        if (self.current_batch_success + self.current_batch_errors) >= self.current_batch_total:
            self._on_batch_complete()

    def _on_task_error(self, task, error_msg):
        """Handle task error (called on main thread)"""
        self.current_batch_errors += 1
        print(f"Generation error for prompt #{task.prompt.id}: {error_msg}")

        if task.is_regen:
            # Sandbox regen error: release lock, show message, don't touch DB
            self.is_generating = False
            self.generate_button.config(state=tk.NORMAL)
            self.current_batch_total = 0
            self.current_batch_success = 0
            self.current_batch_errors = 0
            self._update_history_buttons()
            self.update_status(f"Regen error: {error_msg[:80]}", 'error')
            messagebox.showerror("Regeneration Failed", error_msg)
            return

        try:
            self.prompt_repo.update_artifact_status(task.prompt.id, 'error', error_msg[:2000])
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
        # Refresh history artifact counts too
        if hasattr(self, 'history_tree'):
            self._load_history()

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

        try:
            # Execute workflow
            executor = ImageWorkflowExecutor(self.config)
            artifacts = executor.generate(
                prompt,
                json_data,
                progress_callback=lambda msg: None  # Silent
            )

            # Atomically save all artifacts + update status
            self.artifact_repo.save_artifacts_atomic(
                prompt_id=prompt.id,
                artifacts=artifacts,
                final_status='ready'
            )

        except Exception:
            raise

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

    def _generate_lyrics_prompt_silent(self, prompt: PromptRecord, audio_params: dict = None):
        """Execute audio generation workflow (silent, no dialogs)

        Args:
            prompt: PromptRecord to generate
            audio_params: Optional dict of ACE 1.5 generation parameters from GUI panel
        """
        # Update status to processing
        self.prompt_repo.update_artifact_status(prompt.id, 'processing')

        # Parse JSON data
        json_data = LyricsPromptData.from_json(prompt.get_json_prompt())

        try:
            # Execute workflow
            executor = AudioWorkflowExecutor(self.config)
            artifacts = executor.generate(
                prompt,
                json_data,
                progress_callback=lambda msg: None,  # Silent
                audio_params=audio_params
            )

            # Atomically save all artifacts + update status
            self.artifact_repo.save_artifacts_atomic(
                prompt_id=prompt.id,
                artifacts=artifacts,
                final_status='ready'
            )

        except Exception:
            raise

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

    # ─────────────────────────────────────────────────────────────────────────
    # SHARED EXPORT / PROMOTE HANDLERS  (called from Image and Audio viewers)
    # ─────────────────────────────────────────────────────────────────────────

    def _export_file(self, file_path):
        """Copy the currently selected viewer artifact to a user-chosen location."""
        import shutil
        from tkinter import filedialog
        from pathlib import Path

        file_path = Path(file_path)
        if not file_path.exists():
            messagebox.showerror("File Not Found", f"Cannot find:\n{file_path}")
            return

        ext = file_path.suffix.lower()
        if ext in ('.wav', '.mp3', '.flac'):
            filetypes = [("Audio files", f"*{ext}"), ("All files", "*.*")]
        else:
            filetypes = [("Image files", f"*{ext}"), ("All files", "*.*")]

        dest = filedialog.asksaveasfilename(
            title="Export to…",
            defaultextension=ext,
            initialfile=file_path.name,
            filetypes=filetypes,
        )
        if not dest:
            return

        try:
            shutil.copy2(file_path, dest)
            self.update_status(f"Exported → {dest}", 'success')
            messagebox.showinfo("Export Complete", f"Saved to:\n{dest}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _promote_file(self, file_path, artifact_type: str):
        """Promote the currently selected viewer artifact into prompt_artifacts.

        Parses the prompt_id from the directory name, checks whether the file
        is already in the database, and inserts a new prompt_artifacts row if not.
        """
        from pathlib import Path
        from datetime import datetime

        file_path = Path(file_path)
        output_root = Path(self.config['comfyui']['output_directory'])

        # Parse prompt_id from directory name: "{prompt_id}_{timestamp}"
        dir_name = file_path.parent.name
        try:
            prompt_id = int(dir_name.split('_')[0])
        except (ValueError, IndexError):
            messagebox.showerror(
                "Cannot Promote",
                f"Could not determine prompt ID from path:\n{file_path}\n\n"
                "Expected directory name like '219_20260109T150634'."
            )
            return

        # Relative path for DB storage
        try:
            relative_path = str(file_path.relative_to(output_root))
        except ValueError:
            messagebox.showerror(
                "Cannot Promote",
                f"File is outside the configured output directory:\n{file_path}"
            )
            return

        # Check if this exact file is already in prompt_artifacts
        existing = self.artifact_repo.get_artifacts_for_prompt(prompt_id)
        if any(a.file_path == relative_path for a in existing):
            messagebox.showinfo(
                "Already in Database",
                f"This file is already recorded in the database for prompt #{prompt_id}.\n"
                "The web app is already serving it."
            )
            return

        confirmed = messagebox.askyesno(
            "Promote to Web App",
            f"Add this file to the database for prompt #{prompt_id}?\n\n"
            f"File: {file_path.name}\n\n"
            "The web app will serve this file going forward.\n"
            "The previous file (if any) remains on disk.",
        )
        if not confirmed:
            return

        try:
            artifact = ArtifactRecord(
                id=None,
                prompt_id=prompt_id,
                artifact_type=artifact_type,
                file_path=relative_path,
                preview_path=relative_path if artifact_type == 'image' else None,
                metadata={
                    'file_name': file_path.name,
                    'file_size': file_path.stat().st_size,
                    'promoted_from_viewer': True,
                    'generated_at': datetime.fromtimestamp(
                        file_path.stat().st_mtime).isoformat(),
                },
            )
            self.artifact_repo.promote_artifact(prompt_id, artifact)

            if hasattr(self, 'history_tree'):
                self._load_history()

            self.update_status(
                f"Promoted prompt #{prompt_id} artifact — web app now serves the new file.",
                'success'
            )
            messagebox.showinfo(
                "Promoted",
                f"File recorded in database for prompt #{prompt_id}.\n"
                "The web browse page will now serve this file."
            )
        except Exception as e:
            messagebox.showerror("Promote Failed", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # HISTORY TAB
    # ─────────────────────────────────────────────────────────────────────────

    def _create_history_tab(self):
        """Create Tab 4: History & Regeneration"""
        tab4 = tk.Frame(self.main_notebook, bg=COLORS['bg_panel'])
        self.main_notebook.add(tab4, text="🔁 History")

        # ── Button bar (pack FIRST so it anchors to the bottom) ──────────────
        btn_frame = tk.Frame(tab4, bg=COLORS['bg_secondary'], height=55)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        btn_frame.pack_propagate(False)

        self.history_regen_btn = tk.Button(
            btn_frame, text="🔁 Regenerate Selected",
            command=self._regenerate_history_selected,
            bg=COLORS['accent_solar'], fg=COLORS['text_primary'],
            font=('Helvetica Neue', 11, 'bold'),
            relief=tk.FLAT, bd=0, highlightthickness=0,
            padx=20, pady=10, cursor='hand2', state=tk.DISABLED,
        )
        self.history_regen_btn.pack(side=tk.LEFT, padx=(10, 5), pady=8)

        tk.Label(
            btn_frame,
            text="After regeneration, use Export or Promote in the 🖼 Images / 🎵 Audio tab",
            bg=COLORS['bg_secondary'], fg=COLORS['text_light'],
            font=('Helvetica Neue', 9),
        ).pack(side=tk.LEFT, padx=10)

        # ── Vertical split: list (top) + details (bottom) ────────────────────
        history_paned = tk.PanedWindow(
            tab4, orient=tk.VERTICAL,
            sashrelief=tk.FLAT, bg=COLORS['bg_primary'],
            sashwidth=4, bd=0,
        )
        history_paned.pack(fill=tk.BOTH, expand=True)

        # ── TOP: filter bar + treeview ───────────────────────────────────────
        list_section = tk.Frame(history_paned, bg=COLORS['bg_primary'])

        # Filter bar
        filter_frame = tk.Frame(list_section, bg=COLORS['bg_secondary'], height=40)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        filter_frame.pack_propagate(False)

        tk.Label(filter_frame, text="Show:", bg=COLORS['bg_secondary'],
                 fg=COLORS['text_light'],
                 font=('Helvetica Neue', 11, 'bold')).pack(side=tk.LEFT, padx=(10, 5))

        self.history_filter_var = tk.StringVar(value="All")
        ttk.Combobox(
            filter_frame, textvariable=self.history_filter_var,
            values=["All", "Images", "Audio"],
            state='readonly', width=10,
            style='Solarpunk.TCombobox',
        ).pack(side=tk.LEFT, padx=5)
        self.history_filter_var.trace_add('write', lambda *_: self._load_history())

        tk.Button(
            filter_frame, text="Refresh", command=self._load_history,
            bg=COLORS['bg_secondary'], fg=COLORS['text_light'],
            font=('Helvetica Neue', 10), relief=tk.FLAT, bd=0,
            highlightthickness=0, padx=15, pady=5, cursor='hand2',
        ).pack(side=tk.RIGHT, padx=10)

        tk.Label(
            filter_frame,
            text="Audio params (key, BPM…) are read from the ⚙ Prompts → Audio Params tab",
            bg=COLORS['bg_secondary'], fg=COLORS['text_light'],
            font=('Helvetica Neue', 9),
        ).pack(side=tk.RIGHT, padx=10)

        # Treeview
        tree_frame = ttk.LabelFrame(list_section, text="All Past Prompts",
                                    style='Solarpunk.TLabelframe')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.history_tree = ttk.Treeview(
            tree_frame,
            columns=('icon', 'type', 'id', 'title', 'created', 'status', 'artifacts'),
            show='headings', selectmode='browse',
            style='Solarpunk.Treeview',
        )
        self.history_tree.heading('icon',      text='')
        self.history_tree.heading('type',      text='Type')
        self.history_tree.heading('id',        text='ID')
        self.history_tree.heading('title',     text='Title / Preview')
        self.history_tree.heading('created',   text='Created')
        self.history_tree.heading('status',    text='Status')
        self.history_tree.heading('artifacts', text='Artifacts')

        self.history_tree.column('icon',      width=36,  anchor='center', stretch=False)
        self.history_tree.column('type',      width=70,  anchor='w',      stretch=False)
        self.history_tree.column('id',        width=55,  anchor='center', stretch=False)
        self.history_tree.column('title',     width=340, anchor='w')
        self.history_tree.column('created',   width=140, anchor='w',      stretch=False)
        self.history_tree.column('status',    width=100, anchor='center', stretch=False)
        self.history_tree.column('artifacts', width=72,  anchor='center', stretch=False)

        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=self.history_tree.yview,
                                  style='Solarpunk.Vertical.TScrollbar')
        self.history_tree.configure(yscrollcommand=h_scroll.set)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        h_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_tree.bind('<<TreeviewSelect>>', self._on_history_select)

        history_paned.add(list_section, minsize=200)

        # ── BOTTOM: Details notebook (JSON + Audio Params) ───────────────────
        details_section = tk.Frame(history_paned, bg=COLORS['bg_primary'])

        self.history_details_notebook = ttk.Notebook(
            details_section, style='Solarpunk.TNotebook')
        self.history_details_notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Tab 0: JSON viewer
        json_tab = tk.Frame(self.history_details_notebook, bg=COLORS['bg_panel'])
        self.history_details_notebook.add(json_tab, text="  Details (JSON)  ")

        self.history_details_text = scrolledtext.ScrolledText(
            json_tab, wrap=tk.WORD, font=('Consolas', 11),
            bg=COLORS['bg_panel'], fg=COLORS['text_primary'],
            insertbackground=COLORS['accent_solar'],
            selectbackground=COLORS['selected'],
            selectforeground=COLORS['text_primary'],
            borderwidth=0, highlightthickness=0, padx=10, pady=10,
        )
        self.history_details_text.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Audio params — reuses the shared self._ap_* variables
        audio_tab = tk.Frame(self.history_details_notebook, bg=COLORS['bg_primary'])
        self.history_details_notebook.add(audio_tab, text="  Audio Params (ACE 1.5)  ")
        self._build_audio_params_widgets_only(audio_tab)

        history_paned.add(details_section, minsize=180)

        # Initial load
        self._load_history()

    # ── Status label helpers ──────────────────────────────────────────────────
    _STATUS_LABELS = {
        'ready':      '✓ Ready',
        'pending':    '⏳ Pending',
        'error':      '✗ Error',
        'processing': '⟳ Processing',
    }

    def _load_history(self):
        """Reload history treeview from database"""
        if not hasattr(self, 'history_tree'):
            return

        self.history_tree.delete(*self.history_tree.get_children())

        fval = self.history_filter_var.get()
        type_filter = None
        if fval == 'Images':
            type_filter = 'image_prompt'
        elif fval == 'Audio':
            type_filter = 'lyrics_prompt'

        try:
            prompts = self.prompt_repo.get_all_media_prompts(type_filter=type_filter)
        except Exception as e:
            print(f"History load error: {e}")
            return

        for prompt in prompts:
            icon = self.ICON_MAP.get(prompt.prompt_type, '?')
            type_label = 'Image' if prompt.prompt_type == 'image_prompt' else 'Audio'
            artifact_count = getattr(prompt, '_artifact_count', 0)

            # Title from JSON content
            json_data = prompt.get_json_prompt()
            if prompt.prompt_type == 'image_prompt':
                raw = json_data.get('prompt', prompt.prompt_text or '')
                title = (raw[:60] + '…') if len(raw) > 60 else raw
            else:
                title = json_data.get('title', prompt.prompt_text or '(Untitled)')

            status_label = self._STATUS_LABELS.get(prompt.artifact_status,
                                                    prompt.artifact_status)

            iid = f"hist_{prompt.prompt_type}_{prompt.id}"
            self.history_tree.insert('', 'end', iid=iid, values=(
                icon, type_label, prompt.id, title,
                prompt.created_at.strftime('%Y-%m-%d %H:%M'),
                status_label, artifact_count,
            ))

    def _on_history_select(self, event):
        """Handle row selection in history treeview"""
        selections = self.history_tree.selection()
        if not selections:
            self.history_selected_prompt = None
            self.history_selected_type = None
            self.history_last_regen_artifacts = []
            self._update_history_buttons()
            return

        iid = selections[0]
        # iid format: "hist_{prompt_type}_{id}"
        parts = iid.split('_')
        # parts[0]='hist', parts[1]=type_word, parts[2]=type_word2(if lyrics), parts[-1]=id
        prompt_id = int(parts[-1])
        prompt_type = '_'.join(parts[1:-1])  # 'image_prompt' or 'lyrics_prompt'

        try:
            prompts = self.prompt_repo.get_all_media_prompts(type_filter=prompt_type)
            prompt = next((p for p in prompts if p.id == prompt_id), None)
        except Exception as e:
            print(f"History select error: {e}")
            return

        if not prompt:
            return

        # If the user picks a different prompt, clear any pending regen artifacts
        if (self.history_selected_prompt is None or
                self.history_selected_prompt.id != prompt_id):
            self.history_last_regen_artifacts = []

        self.history_selected_prompt = prompt
        self.history_selected_type = prompt_type

        # Show JSON details
        self.history_details_text.delete('1.0', tk.END)
        json_data = prompt.get_json_prompt()
        self.history_details_text.insert('1.0', json.dumps(json_data, indent=2))

        # Pre-fill shared audio params and switch to the right details tab
        if prompt_type == 'lyrics_prompt':
            self._populate_audio_params_from_prompt(json_data)
            self.history_details_notebook.select(1)   # Show Audio Params
        else:
            self.history_details_notebook.select(0)   # Show JSON only

        self._update_history_buttons()

    def _update_history_buttons(self):
        """Enable/disable History tab buttons based on current state"""
        has_selection = self.history_selected_prompt is not None
        self.history_regen_btn.config(
            state=tk.NORMAL if (has_selection and not self.is_generating) else tk.DISABLED
        )

    def _regenerate_history_selected(self):
        """Queue the selected history prompt for sandbox regeneration (no DB write)"""
        if not self.history_selected_prompt:
            return
        if self.is_generating:
            messagebox.showinfo("Busy", "Please wait for current generation to complete.")
            return

        prompt = self.history_selected_prompt
        prompt_type = self.history_selected_type

        self.is_generating = True
        self.current_batch_total = 1
        self.current_batch_success = 0
        self.current_batch_errors = 0

        audio_params = self._get_audio_params() if prompt_type == 'lyrics_prompt' else None

        task = GenerationTask(
            task_id=1,
            prompt_type=prompt_type,
            prompt=prompt,
            total_in_batch=1,
            position_in_batch=1,
            audio_params=audio_params,
            is_regen=True,
        )
        self.task_queue.put(task)

        label = 'image' if prompt_type == 'image_prompt' else 'audio'
        self.update_status(
            f"Regenerating {label} for prompt #{prompt.id} (sandbox — no DB write)…",
            'processing'
        )
        self.history_regen_btn.config(state=tk.DISABLED)

    def _regen_image_silent(self, prompt: PromptRecord) -> list:
        """Run image executor without touching the database.

        Returns list of ArtifactRecord objects for the generated files.
        """
        json_data = ImagePromptData.from_json(prompt.get_json_prompt())
        executor = ImageWorkflowExecutor(self.config)
        return executor.generate(prompt, json_data, progress_callback=lambda msg: None)

    def _regen_lyrics_silent(self, prompt: PromptRecord, audio_params: dict = None) -> list:
        """Run audio executor without touching the database.

        Returns list of ArtifactRecord objects for the generated files.
        """
        json_data = LyricsPromptData.from_json(prompt.get_json_prompt())
        executor = AudioWorkflowExecutor(self.config)
        return executor.generate(
            prompt, json_data,
            progress_callback=lambda msg: None,
            audio_params=audio_params,
        )

    def _on_regen_complete(self, task: GenerationTask):
        """Called on main thread after a successful sandbox regen task."""
        self.history_last_regen_artifacts = task.regen_artifacts

        # Refresh gallery viewers so the new file appears immediately
        if task.prompt_type == 'image_prompt':
            self.image_gallery.load_images()
            self.main_notebook.select(1)   # Switch to Images tab
        else:
            self.audio_player.load_playlist()
            self.main_notebook.select(2)   # Switch to Audio tab

        # Refresh history artifact count (the file exists on disk but not in DB yet)
        self._load_history()
        self._update_history_buttons()

        label = 'image' if task.prompt_type == 'image_prompt' else 'audio'
        viewer = 'Images' if label == 'image' else 'Audio'
        n = len(task.regen_artifacts)
        self.update_status(
            f"Regenerated {n} {label} file(s) for prompt #{task.prompt.id} — "
            f"select it in the {viewer} tab to Export or Promote.",
            'success'
        )
        messagebox.showinfo(
            "Regeneration Complete",
            f"Generated {n} {label} file(s) for prompt #{task.prompt.id}.\n\n"
            f"The file is now visible in the {viewer} tab.\n"
            f"Select it there to use the Export or Promote buttons."
        )


    # ─────────────────────────────────────────────────────────────────────────

    def run(self):
        """Start application main loop"""
        self.root.mainloop()


def main():
    """Application entry point"""
    # Create root window first (required for proper tkinter hierarchy)
    root = tk.Tk()
    root.withdraw()  # Hide it initially

    # Show splash screen as a Toplevel of root
    splash = SplashScreen(root)

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
        splash.close_splash()
        root.destroy()
        return 1

    # Load configuration
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        splash.close_splash()
        root.destroy()
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
        splash.close_splash()  # Close splash if there's an error
        root.destroy()
        return 1

    print("Configuration validated successfully")
    print(f"Database: {config['database']['path']}")
    print(f"ComfyUI: {config['comfyui']['comfyui_directory']}")
    print()
    print("Launching Media Generator Application...")
    print()

    # Launch application
    try:
        app = MediaGeneratorApp(config, root)  # Pass existing root
        splash.close_splash()  # Close splash screen before showing main app
        root.deiconify()  # Show the main window
        app.run()
        return 0
    except Exception as e:
        print(f"ERROR: Application failed to start: {e}")
        import traceback
        traceback.print_exc()
        splash.close_splash()  # Make sure splash is closed in case of error
        root.destroy()
        return 1


if __name__ == '__main__':
    sys.exit(main())
