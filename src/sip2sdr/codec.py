"""Audio codec identifiers for SIP2SDR.

Only G.711 variants (PCMU and PCMA) are supported, as both operate at
8000 Hz and require no additional transcoding in the audio pipeline.
"""

from enum import Enum


class Codec(Enum):
    """Supported SIP audio codecs.

    Values match the lowercase strings used in the YAML configuration file
    and the PJSUA2 codec identifier prefix (case-insensitive).
    """

    PCMU = "pcmu"  # G.711 µ-law, RTP payload type 0 — default
    PCMA = "pcma"  # G.711 A-law, RTP payload type 8
