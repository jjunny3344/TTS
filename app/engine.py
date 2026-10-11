import io
import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np
import soundfile as sf

from app.config import Settings

logger = logging.getLogger(__name__)


class AudioFormat(str, Enum):
    wav = "wav"
    flac = "flac"
    mp3 = "mp3"
    ogg = "ogg"


# format -> (soundfile format, subtype, media type)
_ENCODINGS = {
    AudioFormat.wav: ("WAV", "PCM_16", "audio/wav"),
    AudioFormat.flac: ("FLAC", "PCM_16", "audio/flac"),
    AudioFormat.mp3: ("MP3", "MPEG_LAYER_III", "audio/mpeg"),
    AudioFormat.ogg: ("OGG", "VORBIS", "audio/ogg"),
}


@dataclass
class SynthesisResult:
    audio: np.ndarray  # mono float32 samples
    sample_rate: int
    duration: float


def encode_audio(result: SynthesisResult, fmt: AudioFormat) -> tuple[bytes, str]:
    sf_format, subtype, media_type = _ENCODINGS[fmt]
    buf = io.BytesIO()
    sf.write(buf, result.audio, result.sample_rate, format=sf_format, subtype=subtype)
    return buf.getvalue(), media_type


class TTSEngine:
    """Thin wrapper around supertonic.TTS that preloads voice styles."""

    def __init__(self, settings: Settings):
        from supertonic import TTS
        from supertonic.config import AVAILABLE_LANGUAGES

        logger.info("Loading Supertonic model '%s'", settings.model)
        self._tts = TTS(
            model=settings.model,
            model_dir=settings.model_dir,
            auto_download=settings.auto_download,
            intra_op_num_threads=settings.intra_op_threads,
        )
        self.model_name = settings.model
        self.sample_rate = self._tts.sample_rate
        self.languages = list(AVAILABLE_LANGUAGES) if self._tts.is_multilingual else ["en"]

        self._styles = {name: self._tts.get_voice_style(name) for name in self._tts.voice_style_names}
        if settings.custom_voices_dir:
            for path in sorted(settings.custom_voices_dir.glob("*.json")):
                self._styles[path.stem] = self._tts.get_voice_style_from_path(path)
        logger.info("Loaded voices: %s", ", ".join(self._styles))

    @property
    def voices(self) -> list[str]:
        return list(self._styles)

    def synthesize(
        self, text: str, voice: str, lang: str, speed: float, steps: int, silence: float
    ) -> SynthesisResult:
        wav, duration = self._tts.synthesize(
            text,
            voice_style=self._styles[voice],
            lang=lang,
            speed=speed,
            total_steps=steps,
            silence_duration=silence,
        )
        return SynthesisResult(
            audio=np.asarray(wav, dtype=np.float32).reshape(-1),
            sample_rate=self.sample_rate,
            duration=float(np.asarray(duration).reshape(-1)[0]),
        )
