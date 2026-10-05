"""Abstract base class for TTS provider implementations."""

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract interface for text-to-speech engine providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        out_path: str,
        voice: str | None = None,
        rate: str = "+0%",
    ) -> None:
        """Synthesize text into speech and save audio to out_path.

        Args:
            text: The text string to synthesize.
            out_path: Destination filepath for the generated audio file.
            voice: Optional voice name or ID. Defaults to language-appropriate voice.
            rate: Speech rate adjustment (e.g., '+0%', '+15%', '-10%').
        """
        pass
