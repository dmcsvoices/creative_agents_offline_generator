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
parser = argparse.ArgumentParser(description='ACE Audio Workflow - Song Generation')
parser.add_argument('--tags', type=str, required=True, help='Song description tags (genre, mood, tempo, etc.)')
parser.add_argument('--lyrics', type=str, required=True, help='Song lyrics with section markers')
parser.add_argument('--output', type=str, required=True, help='Output directory')
parser.add_argument('--comfyui-directory', type=str, help='ComfyUI directory (optional)')
parser.add_argument('--queue-size', type=int, default=1, help='Queue size (default: 1)')

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

    # Creating an instance of PromptServer with the loop
    server_instance = server.PromptServer(loop)
    execution.PromptQueue(server_instance)

    # Initializing custom nodes
    asyncio.run(init_extra_nodes())


def main():
    # Args are already parsed at module level
    # Now initialize ComfyUI
    add_comfyui_directory_to_sys_path()
    add_extra_model_paths()

    # Import nodes AFTER ComfyUI is initialized
    from nodes import NODE_CLASS_MAPPINGS

    # Change to output directory for file saving
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)
    original_dir = os.getcwd()
    os.chdir(output_dir)

    try:
        import_custom_nodes()
        with torch.inference_mode():
            emptyacesteplatentaudio = NODE_CLASS_MAPPINGS["EmptyAceStepLatentAudio"]()
            emptyacesteplatentaudio_17 = emptyacesteplatentaudio.EXECUTE_NORMALIZED(
                seconds=240, batch_size=1
            )

            checkpointloadersimple = NODE_CLASS_MAPPINGS["CheckpointLoaderSimple"]()
            checkpointloadersimple_40 = checkpointloadersimple.load_checkpoint(
                ckpt_name="ace_step_v1_3.5b.safetensors"
            )

            latentoperationtonemapreinhard = NODE_CLASS_MAPPINGS[
                "LatentOperationTonemapReinhard"
            ]()
            latentoperationtonemapreinhard_50 = (
                latentoperationtonemapreinhard.EXECUTE_NORMALIZED(
                    multiplier=1.0000000000000002
                )
            )

            textencodeacestepaudio = NODE_CLASS_MAPPINGS["TextEncodeAceStepAudio"]()
            modelsamplingsd3 = NODE_CLASS_MAPPINGS["ModelSamplingSD3"]()
            latentapplyoperationcfg = NODE_CLASS_MAPPINGS["LatentApplyOperationCFG"]()
            conditioningzeroout = NODE_CLASS_MAPPINGS["ConditioningZeroOut"]()
            ksampler = NODE_CLASS_MAPPINGS["KSampler"]()
            vaedecodeaudio = NODE_CLASS_MAPPINGS["VAEDecodeAudio"]()
            saveaudiomp3 = NODE_CLASS_MAPPINGS["SaveAudioMP3"]()

            for q in range(args.queue_size):
                textencodeacestepaudio_14 = textencodeacestepaudio.EXECUTE_NORMALIZED(
                    tags=args.tags,
                    lyrics=args.lyrics,
                    lyrics_strength=0.9900000000000002,
                    clip=get_value_at_index(checkpointloadersimple_40, 1),
                )

            modelsamplingsd3_51 = modelsamplingsd3.patch(
                shift=5.000000000000001,
                model=get_value_at_index(checkpointloadersimple_40, 0),
            )

            latentapplyoperationcfg_49 = latentapplyoperationcfg.EXECUTE_NORMALIZED(
                model=get_value_at_index(modelsamplingsd3_51, 0),
                operation=get_value_at_index(latentoperationtonemapreinhard_50, 0),
            )

            conditioningzeroout_44 = conditioningzeroout.zero_out(
                conditioning=get_value_at_index(textencodeacestepaudio_14, 0)
            )

            ksampler_52 = ksampler.sample(
                seed=random.randint(1, 2**64),
                steps=50,
                cfg=5,
                sampler_name="euler",
                scheduler="simple",
                denoise=1,
                model=get_value_at_index(latentapplyoperationcfg_49, 0),
                positive=get_value_at_index(textencodeacestepaudio_14, 0),
                negative=get_value_at_index(conditioningzeroout_44, 0),
                latent_image=get_value_at_index(emptyacesteplatentaudio_17, 0),
            )

            vaedecodeaudio_18 = vaedecodeaudio.EXECUTE_NORMALIZED(
                samples=get_value_at_index(ksampler_52, 0),
                vae=get_value_at_index(checkpointloadersimple_40, 2),
            )

            saveaudiomp3_59 = saveaudiomp3.EXECUTE_NORMALIZED(
                filename_prefix="generated_song_",
                quality="V0",
                audioUI="",
                audio=get_value_at_index(vaedecodeaudio_18, 0),
            )

    finally:
        # Restore original directory
        os.chdir(original_dir)


if __name__ == "__main__":
    main()
