"""
config.py — Configuration centralisée de l'agent Akuiteo
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === API ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# === Modèles ===
CLAUDE_MODEL = "claude-opus-4-6"          # Pour le raisonnement ReAct + vision
EMBED_MODEL = "BAAI/bge-m3"               # Multilingue FR/EN, gratuit, local

# === Chemins ===
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = BASE_DIR / "data" / "index"

DOCUMENTS = {
    "livre_blanc":  DATA_DIR / "Extrait_LivreBlanc.docx",
    "cas_usages":   DATA_DIR / "Cas_d_Usages_CRM_Akuiteo_POC.pdf",
    "mode_op_crm":  DATA_DIR / "Mode_operatoire_-_CRM.pdf",   # Mode Opératoire CRM KPMG
}

# === RAG ===
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
TOP_K = 5
SIMILARITY_THRESHOLD = 0.35

# === Agent ===
MAX_ITERATIONS = 8
SYSTEM_PROMPT = """Tu es l'assistant Akuiteo de Rydge Conseil.
Tu aides les collaborateurs à utiliser le logiciel Akuiteo (ERP/CRM de gestion de projets).
Tu as accès à deux outils :
1. rag_search : recherche dans la documentation Akuiteo (procédures, cas d'usage)
2. vision_analysis : analyse de captures d'écran Akuiteo fournies par l'utilisateur

Règles :
- Réponds toujours en français sauf si l'utilisateur parle anglais
- Pour toute question procédurale, utilise d'abord rag_search
- Si une image est fournie, utilise vision_analysis pour l'analyser
- Cite la source documentaire de tes réponses (ex: "Source : Livre Blanc, §3.2")
- Si tu n'es pas sûr, dis-le clairement et propose une recherche complémentaire
"""
