"""
Convert a text script to an MP3 audio file using Edge TTS (free, no API key).
"""

import asyncio
import edge_tts
from pathlib import Path

DEFAULT_VOICE = "en-US-AndrewMultilingualNeural"


async def _text_to_speech(text: str, output_path: Path, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def generate_audio(text: str, output_path: Path, voice: str = DEFAULT_VOICE) -> Path:
    """Convert text to MP3 using Edge TTS. Returns the output path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_text_to_speech(text, output_path, voice))
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Audio saved: {output_path} ({size_mb:.1f} MB)")
    return output_path
