"""
ui/app.py — Interface Streamlit pour l'agent multimodal Akuiteo
Lancer avec : streamlit run ui/app.py
"""
import sys
import logging
from pathlib import Path

import streamlit as st

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INDEX_DIR, DOCUMENTS
from core.rag_engine import AkuiteoRAGEngine
from core.vision_engine import AkuiteoVisionEngine
from core.agent import AkuiteoAgent

# ─── Configuration de la page ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Assistant Akuiteo — Rydge Conseil",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CSS personnalisé ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #00A8D6 0%, #00C4A7 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .tool-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 2px;
    }
    .tool-rag { background: #E8F4FD; color: #1565C0; border: 1px solid #90CAF9; }
    .tool-vision { background: #F3E5F5; color: #6A1B9A; border: 1px solid #CE93D8; }
    .source-box {
        background: #F8F9FA;
        border-left: 3px solid #00A8D6;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 0.8rem;
        margin: 4px 0;
        color: #555;
    }
    .stChatMessage { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)


# ─── Initialisation des composants (cached) ───────────────────────────────────

@st.cache_resource(show_spinner="⚙️ Initialisation de l'index RAG...")
def load_rag_engine() -> AkuiteoRAGEngine:
    """Charge et initialise le moteur RAG (une seule fois, mis en cache)."""
    engine = AkuiteoRAGEngine()
    engine.build_index(force_rebuild=False)
    return engine


@st.cache_resource
def load_vision_engine() -> AkuiteoVisionEngine:
    return AkuiteoVisionEngine()


def get_agent() -> AkuiteoAgent:
    """Récupère ou crée l'agent depuis le session state."""
    if "agent" not in st.session_state:
        rag = load_rag_engine()
        vision = load_vision_engine()
        st.session_state["agent"] = AkuiteoAgent(rag, vision)
    return st.session_state["agent"]


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("### 🗂️ Documents indexés")

        doc_status = {
            "📘 Livre Blanc Akuiteo":       DOCUMENTS["livre_blanc"].exists(),
            "📋 Cas d'Usage CRM (POC)":     DOCUMENTS["cas_usages"].exists(),
            "📊 Mode Opératoire CRM":        DOCUMENTS["mode_op_crm"].exists(),
        }
        for name, exists in doc_status.items():
            icon = "✅" if exists else "❌"
            st.markdown(f"{icon} {name}")

        st.divider()

        # Rebuild de l'index
        if st.button("🔄 Reconstruire l'index RAG", use_container_width=True):
            with st.spinner("Reconstruction en cours..."):
                try:
                    rag = AkuiteoRAGEngine()
                    rag.build_index(force_rebuild=True)
                    # Invalider le cache
                    load_rag_engine.clear()
                    st.session_state.pop("agent", None)
                    st.success("Index reconstruit avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

        st.divider()

        # Reset conversation
        if st.button("🗑️ Nouvelle conversation", use_container_width=True):
            st.session_state["messages"] = []
            if "agent" in st.session_state:
                st.session_state["agent"].reset_conversation()
            st.rerun()

        st.divider()
        st.markdown("**Stack technique**")
        st.markdown("""
        - 🧠 **LLM** : Claude API (Anthropic)  
        - 🔍 **RAG** : LlamaIndex + BGE-M3  
        - 👁️ **Vision** : Claude multimodal  
        - 🔧 **Agent** : ReAct (tool_use)  
        - 🎨 **UI** : Streamlit  
        """)


# ─── Interface principale ─────────────────────────────────────────────────────

def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h2 style="margin:0">🤖 Assistant Akuiteo</h2>
        <p style="margin:4px 0 0 0; opacity:0.85">
            Posez vos questions sur Akuiteo · Joignez une capture d'écran pour une analyse visuelle
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    render_sidebar()

    # Vérification de la configuration
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        st.error("⚠️ **ANTHROPIC_API_KEY** non configurée. Créez un fichier `.env` avec votre clé.")
        st.stop()

    # Initialisation de l'historique des messages
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # ── Affichage de l'historique ──────────────────────────────────────────
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🤖"):
            st.markdown(msg["content"])

            # Affichage des métadonnées (tools utilisés)
            if msg.get("tools_used"):
                tools_html = ""
                for tool in msg["tools_used"]:
                    css_class = "tool-rag" if tool == "rag_search" else "tool-vision"
                    label = "📚 RAG" if tool == "rag_search" else "👁️ Vision"
                    tools_html += f'<span class="tool-badge {css_class}">{label}</span>'
                st.markdown(tools_html, unsafe_allow_html=True)

    # ── Zone de saisie ─────────────────────────────────────────────────────
    col_input, col_upload = st.columns([5, 1])

    with col_upload:
        uploaded_image = st.file_uploader(
            "📎 Capture",
            type=["png", "jpg", "jpeg", "webp"],
            label_visibility="collapsed",
            help="Joignez une capture d'écran Akuiteo pour une analyse visuelle",
        )

    with col_input:
        user_input = st.chat_input(
            "Posez votre question sur Akuiteo... (ex: Comment créer une opportunité ?)"
        )

    # ── Traitement de la question ──────────────────────────────────────────
    if user_input:
        # Affichage du message utilisateur
        display_content = user_input
        if uploaded_image:
            display_content = f"📸 *[Capture d'écran jointe]*\n\n{user_input}"

        st.session_state["messages"].append({
            "role": "user",
            "content": display_content,
        })

        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(display_content)

        # Exécution de l'agent
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analyse en cours..."):
                try:
                    agent = get_agent()

                    # Préparation de l'image si uploadée
                    image_data = None
                    if uploaded_image:
                        # Remettre le pointeur au début (Streamlit UploadedFile)
                        uploaded_image.seek(0)
                        image_data = uploaded_image

                    result = agent.run(
                        user_message=user_input,
                        image_input=image_data,
                    )

                    response_text = result["response"]
                    tools_used = result.get("tools_used", [])
                    iterations = result.get("iterations", 1)

                    # Affichage de la réponse
                    st.markdown(response_text)

                    # Badges des tools utilisés
                    if tools_used:
                        tools_html = ""
                        for tool in tools_used:
                            css_class = "tool-rag" if tool == "rag_search" else "tool-vision"
                            label = "📚 RAG" if tool == "rag_search" else "👁️ Vision"
                            tools_html += f'<span class="tool-badge {css_class}">{label}</span>'
                        tools_html += f'<span style="font-size:0.7rem; color:#999; margin-left:8px">({iterations} iter.)</span>'
                        st.markdown(tools_html, unsafe_allow_html=True)

                    # Sauvegarde dans l'historique
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "tools_used": tools_used,
                    })

                except Exception as e:
                    error_msg = f"❌ Erreur de l'agent : {str(e)}"
                    st.error(error_msg)
                    logger.exception("Erreur agent")
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": error_msg,
                    })

    # ── Questions suggérées ─────────────────────────────────────────────────
    if not st.session_state["messages"]:
        st.markdown("---")
        st.markdown("**💡 Questions suggérées pour démarrer :**")
        suggestions = [
            "Comment créer une nouvelle opportunité dans le CRM ?",
            "Qu'est-ce qu'un Portefeuille dans Akuiteo ?",
            "Comment déplacer une opportunité dans le KANBAN ?",
            "À quoi servent les pictogrammes rouge, vert et orange sur les tuiles ?",
            "Comment rechercher un compte avec des caractères joker ?",
        ]
        cols = st.columns(len(suggestions))
        for i, (col, suggestion) in enumerate(zip(cols, suggestions)):
            with col:
                if st.button(suggestion, key=f"sug_{i}", use_container_width=True):
                    st.session_state["pending_question"] = suggestion
                    st.rerun()

    # Traitement des questions suggérées
    if "pending_question" in st.session_state:
        q = st.session_state.pop("pending_question")
        st.session_state.setdefault("messages", [])
        # Injecter la question comme si l'utilisateur l'avait tapée
        # (le prochain rerun la traitera via chat_input — workaround Streamlit)
        st.info(f"Question sélectionnée : **{q}**\n\nCopiez-la dans le champ de saisie ci-dessus.")


if __name__ == "__main__":
    main()
