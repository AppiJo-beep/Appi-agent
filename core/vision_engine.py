"""
core/vision_engine.py — Analyse de captures d'écran Akuiteo via Claude Vision
"""
import base64
import logging
from pathlib import Path
from io import BytesIO
from typing import Union

import anthropic
from PIL import Image

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

# Prompt système spécialisé pour l'analyse de captures Akuiteo
VISION_SYSTEM_PROMPT = """Tu es un expert en ergonomie du logiciel Akuiteo (ERP/CRM).
Quand on te montre une capture d'écran Akuiteo, tu dois :
1. Identifier précisément le module et le menu visible (ex: CRM > Opportunités)
2. Décrire les éléments d'interface visibles (boutons, menus, données affichées)
3. Identifier si une action est en cours ou un problème visible
4. Expliquer ce que l'utilisateur peut faire depuis cet écran
5. Signaler tout élément inhabituel ou erreur visible

Réponds toujours en français, de manière structurée et pédagogique.
"""


class AkuiteoVisionEngine:
    """
    Moteur d'analyse visuelle pour captures d'écran Akuiteo.
    Utilise Claude Vision (nativement multimodal).
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def analyze_screenshot(
        self,
        image_input: Union[str, bytes, "UploadedFile"],  # Streamlit UploadedFile ou path
        user_question: str = "Qu'est-ce que je vois sur cet écran Akuiteo ?",
        context: str = "",
    ) -> dict:
        """
        Analyse une capture d'écran Akuiteo.

        Args:
            image_input   : Chemin fichier, bytes, ou UploadedFile Streamlit
            user_question : Question spécifique de l'utilisateur sur l'image
            context       : Contexte RAG optionnel pour enrichir l'analyse

        Returns:
            dict avec 'analysis' (str) et 'metadata' (dict)
        """
        try:
            image_data, media_type = self._prepare_image(image_input)
        except Exception as e:
            logger.error(f"❌ Erreur préparation image : {e}")
            return {"analysis": f"Erreur lors du chargement de l'image : {e}", "metadata": {}}

        # Construction du prompt avec contexte RAG si disponible
        prompt_parts = []
        if context:
            prompt_parts.append(
                f"Contexte documentaire Akuiteo pertinent :\n{context}\n\n"
            )
        prompt_parts.append(user_question)
        full_prompt = "".join(prompt_parts)

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=VISION_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": full_prompt,
                            },
                        ],
                    }
                ],
            )

            analysis = response.content[0].text
            return {
                "analysis": analysis,
                "metadata": {
                    "model": CLAUDE_MODEL,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "has_context": bool(context),
                },
            }

        except Exception as e:
            logger.error(f"❌ Erreur API Claude Vision : {e}")
            return {
                "analysis": f"Erreur lors de l'analyse : {e}",
                "metadata": {"error": str(e)},
            }

    def _prepare_image(self, image_input) -> tuple[str, str]:
        """
        Convertit l'image en base64 pour l'API Claude.
        Supporte : chemin fichier (str/Path), bytes bruts, UploadedFile Streamlit.

        Returns:
            (base64_string, media_type)
        """
        # Streamlit UploadedFile
        if hasattr(image_input, "read"):
            raw_bytes = image_input.read()
            name = getattr(image_input, "name", "image.png")
        # Chemin fichier
        elif isinstance(image_input, (str, Path)):
            path = Path(image_input)
            raw_bytes = path.read_bytes()
            name = path.name
        # Bytes bruts
        elif isinstance(image_input, bytes):
            raw_bytes = image_input
            name = "image.png"
        else:
            raise ValueError(f"Type d'image non supporté : {type(image_input)}")

        # Détection du type MIME
        ext = Path(name).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = mime_map.get(ext, "image/png")

        # Redimensionnement si image trop grande (max 5MB pour Claude)
        raw_bytes = self._resize_if_needed(raw_bytes, media_type)

        return base64.standard_b64encode(raw_bytes).decode("utf-8"), media_type

    def _resize_if_needed(self, raw_bytes: bytes, media_type: str, max_size_mb: float = 4.5) -> bytes:
        """Redimensionne l'image si > max_size_mb pour respecter les limites API."""
        if len(raw_bytes) <= max_size_mb * 1024 * 1024:
            return raw_bytes

        logger.info(f"📐 Image trop grande ({len(raw_bytes)/1024/1024:.1f}MB), redimensionnement...")
        img = Image.open(BytesIO(raw_bytes))
        
        # Réduction progressive jusqu'à taille acceptable
        quality = 85
        scale = 0.9
        while len(raw_bytes) > max_size_mb * 1024 * 1024 and scale > 0.2:
            new_size = (int(img.width * scale), int(img.height * scale))
            resized = img.resize(new_size, Image.LANCZOS)
            buf = BytesIO()
            fmt = "JPEG" if "jpeg" in media_type else "PNG"
            resized.save(buf, format=fmt, quality=quality)
            raw_bytes = buf.getvalue()
            scale -= 0.1
            quality = max(60, quality - 5)

        return raw_bytes
