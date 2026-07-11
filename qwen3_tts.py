#!/usr/bin/env python3
"""Qwen3-TTS CLI — voice clone, custom voice, voice design with Qwen3-TTS models."""

import argparse
import os
import sys
from pathlib import Path

import soundfile as sf
import torch
from dotenv import load_dotenv
from qwen_tts import Qwen3TTSModel

load_dotenv(Path(__file__).parent / ".env")

HF_TOKEN = os.getenv("HF_TOKEN")

# Model mapping — each command auto-selects the right model
MODELS = {
    "base-0.6b": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    "customvoice-0.6b": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    "base-1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "customvoice-1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
    "voicedesign-1.7b": "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
}

MODEL_ID = MODELS["base-0.6b"]  # default


def get_device():
    if torch.cuda.is_available():
        return "cuda:0", torch.bfloat16, "flash_attention_2"
    elif torch.backends.mps.is_available():
        return "mps", torch.float32, "sdpa"
    else:
        return "cpu", torch.float32, "sdpa"


def load_model():
    device, dtype, attn = get_device()
    kwargs = dict(
        device_map=device,
        dtype=dtype,
        attn_implementation=attn,
    )
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN

    print(f"Loading {MODEL_ID} on {device} with {dtype}...", file=sys.stderr)
    model = Qwen3TTSModel.from_pretrained(MODEL_ID, **kwargs)
    print("Model loaded.", file=sys.stderr)
    return model, attn


def cmd_voice_clone(args):
    global MODEL_ID
    prev = MODEL_ID
    MODEL_ID = MODELS.get(args.model, MODELS["base-0.6b"])
    try:
        model, _ = load_model()

        ref_audio = args.ref_audio[0] if len(args.ref_audio) == 1 else args.ref_audio
        ref_text = None
        if args.ref_text:
            ref_text = args.ref_text[0] if len(args.ref_text) == 1 else args.ref_text

        if isinstance(ref_audio, list) and len(ref_audio) > 1 and args.x_vector_only and args.merge_refs:
            # Multi-reference: average speaker embeddings for richer voice
            import copy
            prompts = model.create_voice_clone_prompt(
                ref_audio=ref_audio,
                x_vector_only_mode=[True] * len(ref_audio),
            )
            embeddings = [p.ref_spk_embedding for p in prompts]
            avg_emb = torch.stack(embeddings).mean(dim=0)
            combined = copy.copy(prompts[0])
            combined.ref_spk_embedding = avg_emb
            wavs, sr = model.generate_voice_clone(
                text=args.text,
                language=args.language,
                voice_clone_prompt=[combined],
                non_streaming_mode=args.non_streaming,
            )
        else:
            wavs, sr = model.generate_voice_clone(
                text=args.text,
                language=args.language,
                ref_audio=ref_audio,
                ref_text=ref_text,
                x_vector_only_mode=args.x_vector_only,
                non_streaming_mode=args.non_streaming,
            )

        out = args.output or "output_voice_clone.wav"
        sf.write(out, wavs[0], sr)
        print(f"Saved: {out}")
    finally:
        MODEL_ID = prev


def cmd_custom_voice(args):
    global MODEL_ID
    prev = MODEL_ID
    MODEL_ID = MODELS.get(args.model, MODELS["customvoice-0.6b"])
    try:
        model, _ = load_model()

        wavs, sr = model.generate_custom_voice(
            text=args.text,
            speaker=args.speaker,
            language=args.language,
            instruct=args.instruct,
            non_streaming_mode=args.non_streaming,
        )

        out = args.output or "output_custom_voice.wav"
        sf.write(out, wavs[0], sr)
        print(f"Saved: {out}")
    finally:
        MODEL_ID = prev


def cmd_voice_design(args):
    global MODEL_ID
    prev = MODEL_ID
    MODEL_ID = MODELS.get(args.model, MODELS["voicedesign-1.7b"])
    try:
        model, _ = load_model()

        wavs, sr = model.generate_voice_design(
            text=args.text,
            instruct=args.instruct,
            language=args.language,
            non_streaming_mode=args.non_streaming,
        )

        out = args.output or "output_voice_design.wav"
        sf.write(out, wavs[0], sr)
        print(f"Saved: {out}")
    finally:
        MODEL_ID = prev


def cmd_list_languages(args):
    model, _ = load_model()
    langs = model.get_supported_languages()
    if langs:
        print("\n".join(langs))
    else:
        print("English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian")


def cmd_list_speakers(args):
    model, _ = load_model()
    speakers = model.get_supported_speakers()
    if speakers:
        print("\n".join(speakers))
    else:
        print("No built-in speaker list available. Use --instruct for voice design instead.")


def cmd_isolate_vocals(args):
    """Strip background music, keep vocals only using demucs."""
    import subprocess
    audio_path = os.path.abspath(args.input)
    out_dir = args.out_dir or os.path.join(os.path.dirname(audio_path), "separated")
    os.makedirs(out_dir, exist_ok=True)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Isolating vocals from {audio_path}...", file=sys.stderr)
    subprocess.run(
        ["demucs", "--device", device, audio_path, "-o", out_dir],
        check=True,
    )
    # Find output
    base = os.path.splitext(os.path.basename(audio_path))[0]
    vocals_path = os.path.join(out_dir, "htdemucs", base, "vocals.wav")
    if os.path.exists(vocals_path):
        print(f"Vocals saved: {vocals_path}")
    else:
        print(f"Done. Check: {out_dir}/htdemucs/{base}/")


def main():
    parser = argparse.ArgumentParser(description="Qwen3-TTS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # voice-clone
    p = sub.add_parser("voice-clone", help="Clone voice from reference audio")
    p.add_argument("--text", required=True, help="Text to synthesize")
    p.add_argument("--language", default="English", help="Language (default: English)")
    p.add_argument("--ref-audio", required=True, action="append",
                   help="Path/URL to reference audio (repeat for multiple files)")
    p.add_argument("--ref-text", default=None, action="append",
                   help="Transcript of reference audio (repeat, same order as --ref-audio)")
    p.add_argument("--x-vector-only", action="store_true", default=False,
                   help="Extract voice embedding only, no transcript needed")
    p.add_argument("--merge-refs", action="store_true", default=True,
                   help="Average speaker embeddings from multiple refs (default: true)")
    p.add_argument("--output", "-o", default=None, help="Output WAV path")
    p.add_argument("--model", default="base-0.6b",
                   choices=["base-0.6b", "base-1.7b"],
                   help="Model to use (default: base-0.6b)")
    p.add_argument("--non-streaming", action="store_true", default=True, help="Non-streaming mode")
    p.set_defaults(func=cmd_voice_clone)

    # custom-voice
    p = sub.add_parser("custom-voice", help="Generate with built-in speaker")
    p.add_argument("--text", required=True, help="Text to synthesize")
    p.add_argument("--speaker", required=True, help="Speaker name")
    p.add_argument("--language", default="English", help="Language (default: English)")
    p.add_argument("--instruct", default=None, help="Voice instruction (optional)")
    p.add_argument("--output", "-o", default=None, help="Output WAV path")
    p.add_argument("--model", default="customvoice-0.6b",
                   choices=["customvoice-0.6b", "customvoice-1.7b"],
                   help="Model to use (default: customvoice-0.6b)")
    p.add_argument("--non-streaming", action="store_true", default=True, help="Non-streaming mode")
    p.set_defaults(func=cmd_custom_voice)

    # voice-design
    p = sub.add_parser("voice-design", help="Design voice from text description (needs VoiceDesign model)")
    p.add_argument("--text", required=True, help="Text to synthesize")
    p.add_argument("--instruct", required=True, help="Voice description instruction")
    p.add_argument("--language", default="English", help="Language (default: English)")
    p.add_argument("--output", "-o", default=None, help="Output WAV path")
    p.add_argument("--model", default="voicedesign-1.7b",
                   choices=["voicedesign-1.7b"],
                   help="Model to use (default: voicedesign-1.7b)")
    p.add_argument("--non-streaming", action="store_true", default=True, help="Non-streaming mode")
    p.set_defaults(func=cmd_voice_design)

    # list-languages
    p = sub.add_parser("list-languages", help="List supported languages")
    p.set_defaults(func=cmd_list_languages)

    # list-speakers
    p = sub.add_parser("list-speakers", help="List built-in speakers")
    p.set_defaults(func=cmd_list_speakers)

    # isolate-vocals
    p = sub.add_parser("isolate-vocals", help="Strip background music from audio (demucs)")
    p.add_argument("--input", "-i", required=True, help="Input audio file path")
    p.add_argument("--out-dir", "-o", default=None, help="Output directory (default: ./separated)")
    p.set_defaults(func=cmd_isolate_vocals)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
