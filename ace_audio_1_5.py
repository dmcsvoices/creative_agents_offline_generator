import os
import random
import sys
import argparse
from typing import Sequence, Mapping, Any, Union
import torch


def get_value_at_index(obj: Union[Sequence, Mapping], index: int) -> Any:
    """Returns the value at the given index of a sequence or mapping.

    If the object is a sequence (like list or string), returns the value at the given index.
    If the object is a mapping (like a dictionary), returns the value at the index-th key.

    Some return a dictionary, in these cases, we look for the "results" key

    Args:
        obj (Union[Sequence, Mapping]): The object to retrieve the value from.
        index (int): The index of the value to retrieve.

    Returns:
        Any: The value at the given index.

    Raises:
        IndexError: If the index is out of bounds for the object and the object is not a mapping.
    """
    try:
        return obj[index]
    except KeyError:
        return obj["result"][index]


def find_path(name: str, path: str = None) -> str:
    """
    Recursively looks at parent folders starting from the given path until it finds the given name.
    Returns the path as a Path object if found, or None otherwise.
    """
    # If no path is given, use the current working directory
    if path is None:
        path = os.getcwd()

    # Check if the current directory contains the name
    if name in os.listdir(path):
        path_name = os.path.join(path, name)
        print(f"{name} found: {path_name}")
        return path_name

    # Get the parent directory
    parent_directory = os.path.dirname(path)

    # If the parent directory is the same as the current directory, we've reached the root and stop the search
    if parent_directory == path:
        return None

    # Recursively call the function with the parent directory
    return find_path(name, parent_directory)


def add_comfyui_directory_to_sys_path() -> None:
    """
    Add 'ComfyUI' to the sys.path
    """
    # Use command-line argument if provided, otherwise search for it
    if args and args.comfyui_directory:
        comfyui_path = args.comfyui_directory
    else:
        comfyui_path = find_path("ComfyUI")

    if comfyui_path is not None and os.path.isdir(comfyui_path):
        sys.path.append(comfyui_path)
        print(f"'{comfyui_path}' added to sys.path")


def add_extra_model_paths() -> None:
    """
    Parse the optional extra_model_paths.yaml file and add the parsed paths to the sys.path.
    """
    try:
        from main import load_extra_path_config
    except ImportError:
        print(
            "Could not import load_extra_path_config from main.py. Looking in utils.extra_config instead."
        )
        from utils.extra_config import load_extra_path_config

    extra_model_paths = find_path("extra_model_paths.yaml")

    if extra_model_paths is not None:
        load_extra_path_config(extra_model_paths)
    else:
        print("Could not find the extra_model_paths config file.")


# Create argument parser at module level (BEFORE any ComfyUI imports)
parser = argparse.ArgumentParser(description='ACE Audio 1.5 Workflow - Song Generation')
parser.add_argument('--tags', type=str, required=True, help='Song description tags (genre, mood, tempo, etc.)')
parser.add_argument('--lyrics', type=str, required=True, help='Song lyrics with section markers')
parser.add_argument('--output', type=str, required=True, help='Output directory')
parser.add_argument('--comfyui-directory', type=str, help='ComfyUI directory (optional)')
parser.add_argument('--queue-size', type=int, default=1, help='Queue size (default: 1)')
# ACE Step 1.5 generation parameters
parser.add_argument('--bpm', type=int, default=190, help='Beats per minute (default: 190)')
parser.add_argument('--duration', type=int, default=120, help='Duration in seconds (default: 120)')
parser.add_argument('--timesignature', type=str, default='4', help='Time signature numerator (default: 4)')
parser.add_argument('--keyscale', type=str, default='E minor', help='Key and scale, e.g. "E minor" (default: E minor)')
parser.add_argument('--language', type=str, default='en', help='Lyrics language code (default: en)')
parser.add_argument('--cfg-scale', type=float, default=2.0, help='CFG scale (default: 2.0)')
parser.add_argument('--temperature', type=float, default=0.85, help='Sampling temperature (default: 0.85)')
parser.add_argument('--top-p', type=float, default=0.9, help='Top-p nucleus sampling (default: 0.9)')
parser.add_argument('--top-k', type=int, default=0, help='Top-k sampling, 0=disabled (default: 0)')
parser.add_argument('--min-p', type=float, default=0.0, help='Min-p sampling (default: 0.0)')

# Parse args at module level and replace sys.argv with empty args for ComfyUI
# This prevents ComfyUI's argument parser from seeing our custom arguments
args = None
if __name__ == "__main__":
    args = parser.parse_args()
    # Replace sys.argv so ComfyUI doesn't see our custom args
    sys.argv = [sys.argv[0]]


def import_custom_nodes() -> None:
    """Find all custom nodes in the custom_nodes folder and add those node objects to NODE_CLASS_MAPPINGS

    This function sets up a new asyncio event loop, initializes the PromptServer,
    creates a PromptQueue, and initializes the custom nodes.
    """
    import asyncio
    import execution
    from nodes import init_extra_nodes

    sys.path.insert(0, find_path("ComfyUI"))
    import server

    # Creating a new event loop and setting it as the default loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def inner():
        # Creating PromptServer INSIDE the async context so it shares the same event loop
        server_instance = server.PromptServer(loop)
        execution.PromptQueue(server_instance)
        # Initializing custom nodes within the same event loop
        await init_extra_nodes()

    loop.run_until_complete(inner())


def main():
    # Args are already parsed at module level
    # Save original directory
    original_dir = os.getcwd()

    # Change to ComfyUI directory if specified
    if args and args.comfyui_directory:
        os.chdir(args.comfyui_directory)

    # Now initialize ComfyUI
    add_comfyui_directory_to_sys_path()
    add_extra_model_paths()

    # Import nodes AFTER ComfyUI is initialized
    from nodes import NODE_CLASS_MAPPINGS

    # Prepare output directory (but don't change to it yet)
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Import custom nodes while still in ComfyUI directory
        import_custom_nodes()

        # NOW change to output directory for file saving
        os.chdir(output_dir)
        with torch.inference_mode():
            checkpointloadersimple = NODE_CLASS_MAPPINGS["CheckpointLoaderSimple"]()
            checkpointloadersimple_97 = checkpointloadersimple.load_checkpoint(
                ckpt_name="ace_step_1.5_turbo_aio.safetensors"
            )

            emptyacestep15latentaudio = NODE_CLASS_MAPPINGS["EmptyAceStep1.5LatentAudio"]()
            emptyacestep15latentaudio_98 = emptyacestep15latentaudio.EXECUTE_NORMALIZED(
                seconds=args.duration, batch_size=1
            )

            modelsamplingauraflow = NODE_CLASS_MAPPINGS["ModelSamplingAuraFlow"]()
            textencodeacestepaudio15 = NODE_CLASS_MAPPINGS["TextEncodeAceStepAudio1.5"]()
            conditioningzeroout = NODE_CLASS_MAPPINGS["ConditioningZeroOut"]()
            ksampler = NODE_CLASS_MAPPINGS["KSampler"]()
            vaedecodeaudio = NODE_CLASS_MAPPINGS["VAEDecodeAudio"]()

            for q in range(args.queue_size):
                modelsamplingauraflow_78 = modelsamplingauraflow.patch_aura(
                    shift=3, model=get_value_at_index(checkpointloadersimple_97, 0)
                )

                textencodeacestepaudio15_94 = textencodeacestepaudio15.EXECUTE_NORMALIZED(
                    tags=args.tags,
                    lyrics=args.lyrics,
                    seed=random.randint(1, 2**64),
                    bpm=args.bpm,
                    duration=args.duration,
                    timesignature=args.timesignature,
                    language=args.language,
                    keyscale=args.keyscale,
                    generate_audio_codes=True,
                    cfg_scale=args.cfg_scale,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    top_k=args.top_k,
                    min_p=args.min_p,
                    clip=get_value_at_index(checkpointloadersimple_97, 1),
                )

                conditioningzeroout_47 = conditioningzeroout.zero_out(
                    conditioning=get_value_at_index(textencodeacestepaudio15_94, 0)
                )

                ksampler_3 = ksampler.sample(
                    seed=random.randint(1, 2**64),
                    steps=8,
                    cfg=1,
                    sampler_name="euler",
                    scheduler="simple",
                    denoise=1,
                    model=get_value_at_index(modelsamplingauraflow_78, 0),
                    positive=get_value_at_index(textencodeacestepaudio15_94, 0),
                    negative=get_value_at_index(conditioningzeroout_47, 0),
                    latent_image=get_value_at_index(emptyacestep15latentaudio_98, 0),
                )

                vaedecodeaudio_18 = vaedecodeaudio.EXECUTE_NORMALIZED(
                    samples=get_value_at_index(ksampler_3, 0),
                    vae=get_value_at_index(checkpointloadersimple_97, 2),
                )

                # Save audio manually using torchaudio (SaveAudioMP3 requires server context)
                audio_output = get_value_at_index(vaedecodeaudio_18, 0)

                import torchaudio
                from datetime import datetime

                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"GeneratedAudio_{timestamp}_{q:05d}.mp3"
                filepath = os.path.join(output_dir, filename)

                # Audio output is dict with 'waveform' and 'sample_rate'
                waveform = audio_output['waveform']
                sample_rate = audio_output['sample_rate']

                # Ensure waveform is on CPU and has correct shape
                if hasattr(waveform, 'cpu'):
                    waveform = waveform.cpu()

                # Ensure waveform is 2D [channels, samples]
                if waveform.dim() == 3:
                    # Remove batch dimension if present [batch, channels, samples] -> [channels, samples]
                    waveform = waveform.squeeze(0)
                elif waveform.dim() == 1:
                    # Add channel dimension if missing [samples] -> [1, samples]
                    waveform = waveform.unsqueeze(0)

                # Save as MP3 using torchaudio backend
                # Note: For MP3 support, you may need ffmpeg installed
                try:
                    torchaudio.save(filepath, waveform, sample_rate, format="mp3")
                    print(f"Audio saved to: {filepath}")
                except Exception as e:
                    # Fallback to WAV if MP3 encoding fails
                    print(f"Warning: MP3 encoding failed ({e}), saving as WAV instead")
                    wav_filepath = filepath.replace('.mp3', '.wav')
                    torchaudio.save(wav_filepath, waveform, sample_rate)
                    print(f"Audio saved to: {wav_filepath}")

    finally:
        # Restore original directory
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
