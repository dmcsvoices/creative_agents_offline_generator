import os
import random
import sys
import json
import argparse
import contextlib
from typing import Sequence, Mapping, Any, Union
import torch

# Initialize has_manager flag (fixes SaveAsScript bug where this isn't initialized)
has_manager = False


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
        if args is None or args.comfyui_directory is None:
            path = os.getcwd()
        else:
            path = args.comfyui_directory

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

        manager_path = os.path.join(
            comfyui_path, "custom_nodes", "ComfyUI-Manager", "glob"
        )

        if os.path.isdir(manager_path) and os.listdir(manager_path):
            sys.path.append(manager_path)
            global has_manager
            has_manager = True

        import __main__

        if getattr(__main__, "__file__", None) is None:
            __main__.__file__ = os.path.join(comfyui_path, "main.py")

        print(f"'{comfyui_path}' added to sys.path")


def add_extra_model_paths() -> None:
    """
    Parse the optional extra_model_paths.yaml file and add the parsed paths to the sys.path.
    """
    from comfy.options import enable_args_parsing

    enable_args_parsing()
    from utils.extra_config import load_extra_path_config

    extra_model_paths = find_path("extra_model_paths.yaml")

    if extra_model_paths is not None:
        load_extra_path_config(extra_model_paths)
    else:
        print("Could not find the extra_model_paths config file.")


def import_custom_nodes() -> None:
    """Find all custom nodes in the custom_nodes folder and add those node objects to NODE_CLASS_MAPPINGS

    This function sets up a new asyncio event loop, initializes the PromptServer,
    creates a PromptQueue, and initializes the custom nodes.
    """
    if has_manager:
        try:
            import manager_core as manager
        except ImportError:
            print("Could not import manager_core, proceeding without it.")
            return
        else:
            if hasattr(manager, "get_config"):
                print("Patching manager_core.get_config to enforce offline mode.")
                try:
                    get_config = manager.get_config

                    def _get_config(*args, **kwargs):
                        config = get_config(*args, **kwargs)
                        config["network_mode"] = "offline"
                        return config

                    manager.get_config = _get_config
                except Exception as e:
                    print("Failed to patch manager_core.get_config:", e)

    import asyncio
    import execution
    from nodes import init_extra_nodes
    import server

    # Creating a new event loop and setting it as the default loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def inner():
        # Creating an instance of PromptServer with the loop
        server_instance = server.PromptServer(loop)
        execution.PromptQueue(server_instance)

        # Initializing custom nodes
        await init_extra_nodes(init_custom_nodes=True)

    loop.run_until_complete(inner())


def save_image_wrapper(context, cls):
    if args.output is None:
        return cls

    from PIL import Image, ImageOps, ImageSequence
    from PIL.PngImagePlugin import PngInfo

    import numpy as np

    class WrappedSaveImage(cls):
        counter = 0

        def save_images(
            self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None
        ):
            if args.output is None:
                return super().save_images(
                    images, filename_prefix, prompt, extra_pnginfo
                )
            else:
                if len(images) > 1 and args.output == "-":
                    raise ValueError("Cannot save multiple images to stdout")
                filename_prefix += self.prefix_append

                results = list()
                for batch_number, image in enumerate(images):
                    i = 255.0 * image.cpu().numpy()
                    img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                    metadata = None
                    if not args.disable_metadata:
                        metadata = PngInfo()
                        if prompt is not None:
                            metadata.add_text("prompt", json.dumps(prompt))
                        if extra_pnginfo is not None:
                            for x in extra_pnginfo:
                                metadata.add_text(x, json.dumps(extra_pnginfo[x]))

                    if args.output == "-":
                        # Hack to briefly restore stdout
                        if context is not None:
                            context.__exit__(None, None, None)
                        try:
                            img.save(
                                sys.stdout.buffer,
                                format="png",
                                pnginfo=metadata,
                                compress_level=self.compress_level,
                            )
                        finally:
                            if context is not None:
                                context.__enter__()
                    else:
                        subfolder = ""
                        if len(images) == 1:
                            if os.path.isdir(args.output):
                                subfolder = args.output
                                file = "output.png"
                            else:
                                subfolder, file = os.path.split(args.output)
                                if subfolder == "":
                                    subfolder = os.getcwd()
                        else:
                            if os.path.isdir(args.output):
                                subfolder = args.output
                                file = filename_prefix
                            else:
                                subfolder, file = os.path.split(args.output)

                            if subfolder == "":
                                subfolder = os.getcwd()

                            files = os.listdir(subfolder)
                            file_pattern = file
                            while True:
                                filename_with_batch_num = file_pattern.replace(
                                    "%batch_num%", str(batch_number)
                                )
                                file = (
                                    f"{filename_with_batch_num}_{self.counter:05}.png"
                                )
                                self.counter += 1

                                if file not in files:
                                    break

                        img.save(
                            os.path.join(subfolder, file),
                            pnginfo=metadata,
                            compress_level=self.compress_level,
                        )
                        print("Saved image to", os.path.join(subfolder, file))
                        results.append(
                            {
                                "filename": file,
                                "subfolder": subfolder,
                                "type": self.type,
                            }
                        )

                return {"ui": {"images": results}}

    return WrappedSaveImage


def parse_arg(s: Any, default: Any = None) -> Any:
    """Parses a JSON string, returning it unchanged if the parsing fails."""
    if __name__ == "__main__" or not isinstance(s, str):
        return s

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return s


parser = argparse.ArgumentParser(
    description="A converted ComfyUI workflow. Node inputs listed below. Values passed should be valid JSON (assumes string if not valid JSON)."
)
parser.add_argument(
    "--clip_name1",
    default="qwen_3_4b.safetensors",
    help='Argument 0, input `clip_name` for node "Load CLIP" id 39 (autogenerated)',
)

parser.add_argument(
    "--type2",
    default="lumina2",
    help='Argument 1, input `type` for node "Load CLIP" id 39 (autogenerated)',
)

parser.add_argument(
    "--vae_name3",
    default="ae.safetensors",
    help='Argument 0, input `vae_name` for node "Load VAE" id 40 (autogenerated)',
)

parser.add_argument(
    "--width4",
    default=768,
    help='Argument 0, input `width` for node "EmptySD3LatentImage" id 41 (autogenerated)',
)

parser.add_argument(
    "--height5",
    default=1024,
    help='Argument 1, input `height` for node "EmptySD3LatentImage" id 41 (autogenerated)',
)

parser.add_argument(
    "--batch_size6",
    default=1,
    help='Argument 2, input `batch_size` for node "EmptySD3LatentImage" id 41 (autogenerated)',
)

parser.add_argument(
    "--text7",
    default="Side view shot of strikingly beautiful Latina female with thick wavy hair, Professional and sofisticated wearing a tight fitting skirt suit. Her large breasts burst from the top of her white blouse, the top three buttons undone. She wears dark sheer pantyhose and stilleto heels. She pushes a shopping cart and stands in a brightly lit produce section of the store. The scene is lit by high florescent lights. ",
    help='Argument 0, input `text` for node "CLIP Text Encode (Prompt)" id 45 (autogenerated)',
)

parser.add_argument(
    "--unet_name8",
    default="z_image_turbo_bf16.safetensors",
    help='Argument 0, input `unet_name` for node "Load Diffusion Model" id 46 (autogenerated)',
)

parser.add_argument(
    "--weight_dtype9",
    default="default",
    help='Argument 1, input `weight_dtype` for node "Load Diffusion Model" id 46 (autogenerated)',
)

parser.add_argument(
    "--shift10",
    default=3,
    help='Argument 1, input `shift` for node "ModelSamplingAuraFlow" id 47 (autogenerated)',
)

parser.add_argument(
    "--seed11",
    default=397889736320838,
    help='Argument 1, input `seed` for node "KSampler" id 44 (autogenerated)',
)

parser.add_argument(
    "--steps12",
    default=9,
    help='Argument 2, input `steps` for node "KSampler" id 44 (autogenerated)',
)

parser.add_argument(
    "--cfg13",
    default=1,
    help='Argument 3, input `cfg` for node "KSampler" id 44 (autogenerated)',
)

parser.add_argument(
    "--sampler_name14",
    default="res_multistep",
    help='Argument 4, input `sampler_name` for node "KSampler" id 44 (autogenerated)',
)

parser.add_argument(
    "--scheduler15",
    default="simple",
    help='Argument 5, input `scheduler` for node "KSampler" id 44 (autogenerated)',
)

parser.add_argument(
    "--denoise16",
    default=1,
    help='Argument 9, input `denoise` for node "KSampler" id 44 (autogenerated)',
)

parser.add_argument(
    "--filename_prefix17",
    default="z-image",
    help='Argument 1, input `filename_prefix` for node "Save Image" id 9 (autogenerated)',
)

parser.add_argument(
    "--queue-size",
    "-q",
    type=int,
    default=1,
    help="How many times the workflow will be executed (default: 1)",
)

parser.add_argument(
    "--comfyui-directory",
    "-c",
    default=None,
    help="Where to look for ComfyUI (default: current directory)",
)

parser.add_argument(
    "--output",
    "-o",
    default=None,
    help="The location to save the output image. Either a file path, a directory, or - for stdout (default: the ComfyUI output directory)",
)

parser.add_argument(
    "--disable-metadata",
    action="store_true",
    help="Disables writing workflow metadata to the outputs",
)


comfy_args = [sys.argv[0]]
if __name__ == "__main__" and "--" in sys.argv:
    idx = sys.argv.index("--")
    comfy_args += sys.argv[idx + 1 :]
    sys.argv = sys.argv[:idx]

args = None
if __name__ == "__main__":
    args = parser.parse_args()
    sys.argv = comfy_args
if args is not None and args.output is not None and args.output == "-":
    ctx = contextlib.redirect_stdout(sys.stderr)
else:
    ctx = contextlib.nullcontext()

PROMPT_DATA = json.loads(
    '{"9": {"inputs": {"filename_prefix": "z-image", "images": ["43", 0]}, "class_type": "SaveImage", "_meta": {"title": "Save Image"}}, "39": {"inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}, "class_type": "CLIPLoader", "_meta": {"title": "Load CLIP"}}, "40": {"inputs": {"vae_name": "ae.safetensors"}, "class_type": "VAELoader", "_meta": {"title": "Load VAE"}}, "41": {"inputs": {"width": 768, "height": 1024, "batch_size": 1}, "class_type": "EmptySD3LatentImage", "_meta": {"title": "EmptySD3LatentImage"}}, "42": {"inputs": {"conditioning": ["45", 0]}, "class_type": "ConditioningZeroOut", "_meta": {"title": "ConditioningZeroOut"}}, "43": {"inputs": {"samples": ["44", 0], "vae": ["40", 0]}, "class_type": "VAEDecode", "_meta": {"title": "VAE Decode"}}, "44": {"inputs": {"seed": 397889736320838, "steps": 9, "cfg": 1, "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1, "model": ["47", 0], "positive": ["45", 0], "negative": ["42", 0], "latent_image": ["41", 0]}, "class_type": "KSampler", "_meta": {"title": "KSampler"}}, "45": {"inputs": {"text": "Side view shot of strikingly beautiful Latina female with thick wavy hair, Professional and sofisticated wearing a tight fitting skirt suit. Her large breasts burst from the top of her white blouse, the top three buttons undone. She wears dark sheer pantyhose and stilleto heels. She pushes a shopping cart and stands in a brightly lit produce section of the store. The scene is lit by high florescent lights. ", "clip": ["39", 0]}, "class_type": "CLIPTextEncode", "_meta": {"title": "CLIP Text Encode (Prompt)"}}, "46": {"inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader", "_meta": {"title": "Load Diffusion Model"}}, "47": {"inputs": {"shift": 3, "model": ["46", 0]}, "class_type": "ModelSamplingAuraFlow", "_meta": {"title": "ModelSamplingAuraFlow"}}}'
)


def import_custom_nodes() -> None:
    """Find all custom nodes in the custom_nodes folder and add those node objects to NODE_CLASS_MAPPINGS

    This function sets up a new asyncio event loop, initializes the PromptServer,
    creates a PromptQueue, and initializes the custom nodes.
    """
    if has_manager:
        try:
            import manager_core as manager
        except ImportError:
            print("Could not import manager_core, proceeding without it.")
            return
        else:
            if hasattr(manager, "get_config"):
                print("Patching manager_core.get_config to enforce offline mode.")
                try:
                    get_config = manager.get_config

                    def _get_config(*args, **kwargs):
                        config = get_config(*args, **kwargs)
                        config["network_mode"] = "offline"
                        return config

                    manager.get_config = _get_config
                except Exception as e:
                    print("Failed to patch manager_core.get_config:", e)

    import asyncio
    import execution
    from nodes import init_extra_nodes
    import server

    # Creating a new event loop and setting it as the default loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def inner():
        # Creating an instance of PromptServer with the loop
        server_instance = server.PromptServer(loop)
        execution.PromptQueue(server_instance)

        # Initializing custom nodes
        await init_extra_nodes(init_custom_nodes=True)

    loop.run_until_complete(inner())


_custom_nodes_imported = False
_custom_path_added = False


def main(*func_args, **func_kwargs):
    global args, _custom_nodes_imported, _custom_path_added
    if __name__ == "__main__":
        if args is None:
            args = parser.parse_args()
    else:
        defaults = dict(
            (arg, parser.get_default(arg))
            for arg in ["queue_size", "comfyui_directory", "output", "disable_metadata"]
            + [
                "clip_name1",
                "type2",
                "vae_name3",
                "width4",
                "height5",
                "batch_size6",
                "text7",
                "unet_name8",
                "weight_dtype9",
                "shift10",
                "seed11",
                "steps12",
                "cfg13",
                "sampler_name14",
                "scheduler15",
                "denoise16",
                "filename_prefix17",
            ]
        )

        all_args = dict()
        all_args.update(defaults)
        all_args.update(func_kwargs)

        args = argparse.Namespace(**all_args)

    with ctx:
        if not _custom_path_added:
            add_comfyui_directory_to_sys_path()
            add_extra_model_paths()

            _custom_path_added = True

        if not _custom_nodes_imported:
            import_custom_nodes()

            _custom_nodes_imported = True

        from nodes import NODE_CLASS_MAPPINGS

    with torch.inference_mode(), ctx:
        cliploader = NODE_CLASS_MAPPINGS["CLIPLoader"]()
        cliploader_39 = cliploader.load_clip(
            clip_name=parse_arg(args.clip_name1),
            type=parse_arg(args.type2),
            device="default",
        )

        vaeloader = NODE_CLASS_MAPPINGS["VAELoader"]()
        vaeloader_40 = vaeloader.load_vae(vae_name=parse_arg(args.vae_name3))

        emptysd3latentimage = NODE_CLASS_MAPPINGS["EmptySD3LatentImage"]()
        emptysd3latentimage_41 = emptysd3latentimage.EXECUTE_NORMALIZED(
            width=parse_arg(args.width4),
            height=parse_arg(args.height5),
            batch_size=parse_arg(args.batch_size6),
        )

        cliptextencode = NODE_CLASS_MAPPINGS["CLIPTextEncode"]()
        cliptextencode_45 = cliptextencode.encode(
            text=parse_arg(args.text7), clip=get_value_at_index(cliploader_39, 0)
        )

        unetloader = NODE_CLASS_MAPPINGS["UNETLoader"]()
        unetloader_46 = unetloader.load_unet(
            unet_name=parse_arg(args.unet_name8),
            weight_dtype=parse_arg(args.weight_dtype9),
        )

        modelsamplingauraflow = NODE_CLASS_MAPPINGS["ModelSamplingAuraFlow"]()
        conditioningzeroout = NODE_CLASS_MAPPINGS["ConditioningZeroOut"]()
        ksampler = NODE_CLASS_MAPPINGS["KSampler"]()
        vaedecode = NODE_CLASS_MAPPINGS["VAEDecode"]()
        saveimage = save_image_wrapper(ctx, NODE_CLASS_MAPPINGS["SaveImage"])()
        for q in range(args.queue_size):
            modelsamplingauraflow_47 = modelsamplingauraflow.patch_aura(
                shift=parse_arg(args.shift10),
                model=get_value_at_index(unetloader_46, 0),
            )

            conditioningzeroout_42 = conditioningzeroout.zero_out(
                conditioning=get_value_at_index(cliptextencode_45, 0)
            )

            ksampler_44 = ksampler.sample(
                seed=parse_arg(args.seed11),
                steps=parse_arg(args.steps12),
                cfg=parse_arg(args.cfg13),
                sampler_name=parse_arg(args.sampler_name14),
                scheduler=parse_arg(args.scheduler15),
                denoise=parse_arg(args.denoise16),
                model=get_value_at_index(modelsamplingauraflow_47, 0),
                positive=get_value_at_index(cliptextencode_45, 0),
                negative=get_value_at_index(conditioningzeroout_42, 0),
                latent_image=get_value_at_index(emptysd3latentimage_41, 0),
            )

            vaedecode_43 = vaedecode.decode(
                samples=get_value_at_index(ksampler_44, 0),
                vae=get_value_at_index(vaeloader_40, 0),
            )

            if __name__ != "__main__":
                return dict(
                    filename_prefix=parse_arg(args.filename_prefix17),
                    images=get_value_at_index(vaedecode_43, 0),
                    prompt=PROMPT_DATA,
                )
            else:
                saveimage_9 = saveimage.save_images(
                    filename_prefix=parse_arg(args.filename_prefix17),
                    images=get_value_at_index(vaedecode_43, 0),
                    prompt=PROMPT_DATA,
                )


if __name__ == "__main__":
    main()
