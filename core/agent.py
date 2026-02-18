"""
core/agent.py — Agent ReAct Akuiteo avec tools RAG + Vision
Architecture : ReAct loop manuel via Claude API (tool_use)
"""
import json
import logging
from pathlib import Path
from typing import Optional, Union

import anthropic

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_ITERATIONS, SYSTEM_PROMPT
from core.rag_engine import AkuiteoRAGEngine
from core.vision_engine import AkuiteoVisionEngine

logger = logging.getLogger(__name__)

# ─── Définition des tools pour l'API Claude ───────────────────────────────────

TOOLS = [
    {
        "name": "rag_search",
        "description": (
            "Recherche dans la documentation Akuiteo (Livre Blanc, Mode Opératoire CRM, "
            "Cas d'Usage). Utiliser pour toute question sur les procédures, l'ergonomie, "
            "le vocabulaire, ou les fonctionnalités d'Akuiteo. "
            "Retourne les passages documentaires les plus pertinents avec leurs sources."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La question ou les mots-clés à rechercher dans la documentation Akuiteo",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "vision_analysis",
        "description": (
            "Analyse une capture d'écran Akuiteo fournie par l'utilisateur. "
            "Utiliser UNIQUEMENT si l'utilisateur a joint une image dans sa question. "
            "Identifie le module, les éléments d'interface, et explique ce que l'utilisateur voit."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question spécifique à poser sur l'image (ex: 'Quel est le problème visible ?')",
                },
                "rag_context": {
                    "type": "string",
                    "description": "Contexte documentaire optionnel issu du RAG pour enrichir l'analyse visuelle",
                    "default": "",
                },
            },
            "required": ["question"],
        },
    },
]


# ─── Agent ReAct ───────────────────────────────────────────────────────────────

class AkuiteoAgent:
    """
    Agent conversationnel Akuiteo.
    
    Implémente un ReAct loop (Reason + Act) via l'API Claude tool_use.
    - Tool 1 : rag_search  → recherche documentaire vectorielle
    - Tool 2 : vision_analysis → analyse Claude Vision sur captures Akuiteo
    """

    def __init__(self, rag_engine: AkuiteoRAGEngine, vision_engine: AkuiteoVisionEngine):
        self.rag = rag_engine
        self.vision = vision_engine
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.conversation_history = []

    def reset_conversation(self):
        """Réinitialise l'historique de conversation."""
        self.conversation_history = []

    def run(
        self,
        user_message: str,
        image_input: Optional[Union[str, bytes]] = None,
    ) -> dict:
        """
        Point d'entrée principal de l'agent.

        Args:
            user_message : Question texte de l'utilisateur
            image_input  : Capture d'écran Akuiteo optionnelle

        Returns:
            dict avec 'response' (str), 'tools_used' (list), 'iterations' (int)
        """
        # Construction du message utilisateur (texte + image si fournie)
        user_content = self._build_user_content(user_message, image_input)
        self.conversation_history.append({"role": "user", "content": user_content})

        tools_used = []
        iterations = 0

        # ── ReAct Loop ────────────────────────────────────────────────────────
        while iterations < MAX_ITERATIONS:
            iterations += 1

            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.conversation_history,
            )

            # Pas d'appel de tool → réponse finale
            if response.stop_reason == "end_turn":
                final_text = self._extract_text(response)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })
                return {
                    "response": final_text,
                    "tools_used": tools_used,
                    "iterations": iterations,
                }

            # Traitement des tool_use blocks
            if response.stop_reason == "tool_use":
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content,
                })

                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input
                    tools_used.append(tool_name)

                    logger.info(f"🔧 Tool appelé : {tool_name} | Input : {tool_input}")

                    # ── Exécution du tool ──────────────────────────────────
                    if tool_name == "rag_search":
                        result = self._run_rag_search(tool_input.get("query", ""))

                    elif tool_name == "vision_analysis":
                        if image_input is None:
                            result = "⚠️ Aucune image n'a été fournie par l'utilisateur. Impossible d'analyser."
                        else:
                            result = self._run_vision_analysis(
                                image_input=image_input,
                                question=tool_input.get("question", user_message),
                                rag_context=tool_input.get("rag_context", ""),
                            )
                    else:
                        result = f"Tool inconnu : {tool_name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                # Ajout des résultats tools dans l'historique
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results,
                })

        # Fallback si MAX_ITERATIONS atteint
        logger.warning(f"⚠️ MAX_ITERATIONS ({MAX_ITERATIONS}) atteint.")
        return {
            "response": "Je n'ai pas pu finaliser la réponse dans le nombre d'itérations autorisé. Reformulez votre question.",
            "tools_used": tools_used,
            "iterations": iterations,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_user_content(self, text: str, image_input=None) -> list | str:
        """Construit le contenu du message utilisateur (texte ± image)."""
        if image_input is None:
            return text

        # Message multimodal avec image
        try:
            from core.vision_engine import AkuiteoVisionEngine
            img_b64, media_type = self.vision._prepare_image(image_input)
            return [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": img_b64,
                    },
                },
                {"type": "text", "text": text},
            ]
        except Exception as e:
            logger.warning(f"Impossible d'intégrer l'image dans le message : {e}")
            return text

    def _run_rag_search(self, query: str) -> str:
        """Exécute une recherche RAG et formate le résultat pour Claude."""
        try:
            result = self.rag.query(query)
            if not result["passages"]:
                return "Aucun passage pertinent trouvé dans la documentation Akuiteo pour cette requête."

            formatted = []
            for i, (passage, source) in enumerate(zip(result["passages"], result["sources"]), 1):
                formatted.append(f"[{i}] Source : {source}\n{passage}")

            return "\n\n---\n\n".join(formatted)
        except Exception as e:
            logger.error(f"Erreur RAG : {e}")
            return f"Erreur lors de la recherche documentaire : {e}"

    def _run_vision_analysis(self, image_input, question: str, rag_context: str = "") -> str:
        """Exécute l'analyse vision et formate le résultat."""
        try:
            result = self.vision.analyze_screenshot(
                image_input=image_input,
                user_question=question,
                context=rag_context,
            )
            analysis = result.get("analysis", "Analyse indisponible.")
            meta = result.get("metadata", {})
            tokens_info = f"[Tokens: {meta.get('input_tokens', '?')} in / {meta.get('output_tokens', '?')} out]"
            return f"{analysis}\n\n{tokens_info}"
        except Exception as e:
            logger.error(f"Erreur Vision : {e}")
            return f"Erreur lors de l'analyse de l'image : {e}"

    def _extract_text(self, response) -> str:
        """Extrait le texte de la réponse finale de l'API."""
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        return "\n".join(text_parts) if text_parts else "Pas de réponse générée."
