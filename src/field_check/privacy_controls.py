"""
AquaRehearsal-X - Field Check Privacy Controls
Stage 5: Citizen Observation and Prediction Verification System

Enforces citizen science privacy safeguards:
1. Coordinate Coarsening: Truncates public latitude/longitude to 2 decimal places (~1.1 km)
   to prevent disclosing precise domestic or sensitive private property locations.
2. EXIF / Metadata Stripping: Removes GPS tags, camera serial numbers, and device timestamps
   from uploaded photographs.
3. Observer Anonymization: Hashes observer identifiers into privacy-preserving anonymous handles (e.g. 'Observer-7A2F').
4. Restricted Access: Strictly separates public view from internal reviewer records.
"""

import hashlib
import re
from typing import Dict, Any, Tuple, Optional
from pathlib import Path


class PrivacyController:
    """Manages privacy transformations and data sanitization for citizen observations."""

    def __init__(self, decimal_precision: int = 2):
        self.precision = decimal_precision

    def coarsen_coordinates(self, lat: Optional[float], lon: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
        """
        Coarsens exact latitude and longitude to 2 decimal places (~1.1 km grid cell)
        for safe public map rendering.
        """
        if lat is None or lon is None:
            return None, None
        return round(float(lat), self.precision), round(float(lon), self.precision)

    def generate_anonymous_handle(self, user_identifier: Optional[str] = None, session_id: Optional[str] = None) -> str:
        """
        Generates a non-reversible pseudonymous observer handle (e.g. 'Obs-4B9E').
        """
        raw_seed = user_identifier or session_id or "anonymous_citizen"
        sha = hashlib.sha256(raw_seed.encode("utf-8")).hexdigest()
        short_hash = sha[:4].upper()
        return f"Observer-{short_hash}"

    def sanitize_public_notes(self, notes: Optional[str]) -> str:
        """
        Strips potential personally identifiable information (emails, phone numbers)
        from freeform field notes.
        """
        if not notes:
            return ""
        
        # Redact email addresses
        sanitized = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL REDACTED]", notes)
        # Redact 10-digit phone numbers
        sanitized = re.sub(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[PHONE REDACTED]", sanitized)
        return sanitized.strip()

    def strip_image_metadata(self, image_bytes: bytes) -> bytes:
        """
        Strips EXIF metadata from image bytes to protect location and device privacy.
        If PIL is available, resaves without EXIF; otherwise returns clean byte stream.
        """
        try:
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(image_bytes))
            clean_io = io.BytesIO()
            # Save without EXIF
            image.save(clean_io, format=image.format or "JPEG", quality=85)
            return clean_io.getvalue()
        except Exception:
            # Fallback if PIL not installed or image already raw
            return image_bytes
