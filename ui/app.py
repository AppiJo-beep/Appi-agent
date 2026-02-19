"""
ui/app.py — Interface Streamlit pour Appi - Compagnon d'apprentissage Akuiteo
Lancer avec : streamlit run ui/app.py
"""
import sys
import json
import logging
import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INDEX_DIR, DOCUMENTS
from core.rag_engine import AkuiteoRAGEngine
from core.vision_engine import AkuiteoVisionEngine
from core.agent import AkuiteoAgent

# ─── Configuration de la page ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Appi — Compagnon d'apprentissage Akuiteo",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── CSS personnalisé ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    .main-header {
        background: linear-gradient(135deg, #0F4C81 0%, #00A8D6 60%, #00C4A7 100%);
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 4px 20px rgba(0,168,214,0.25);
    }
    .main-header h2 { margin:0; font-size: 1.8rem; font-weight: 700; letter-spacing: -0.5px; }
    .main-header p { margin:6px 0 0 0; opacity:0.9; font-size: 0.95rem; }
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
    .feedback-box {
        background: #F0FBF8;
        border: 1px solid #00C4A7;
        border-radius: 12px;
        padding: 12px 16px;
        margin-top: 12px;
    }
    .ticket-box {
        background: #FFF8E1;
        border: 1px solid #FFB300;
        border-radius: 12px;
        padding: 12px 16px;
        margin-top: 8px;
    }
    .paste-zone {
        border: 2px dashed #00A8D6;
        border-radius: 12px;
        padding: 24px 16px;
        text-align: center;
        color: #FFFFFF;
        font-size: 0.95rem;
        margin-bottom: 8px;
        background: rgba(0, 168, 214, 0.15);
        cursor: pointer;
        transition: all 0.2s;
    }
    .paste-zone:hover {
        background: rgba(0, 168, 214, 0.25);
        border-color: #00C4A7;
    }

# ─── Composant copier-coller image (JS) ───────────────────────────────────────
PASTE_COMPONENT = """
<div class="paste-zone" id="paste-zone">
    <strong style="font-size:1.05rem">Zone de collage &mdash; Ctrl+V ici</strong><br>
    <span style="opacity:0.8; font-size:0.85rem">Copiez une capture d'ecran puis cliquez dans cette zone et faites Ctrl+V</span>
</div>
<canvas id="paste-canvas" style="display:none; max-width:100%; border-radius:8px; margin-top:8px;"></canvas>
<script>
(function() {
    const zone = document.getElementById('paste-zone');
    const canvas = document.getElementById('paste-canvas');

    document.addEventListener('paste', function(e) {
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const blob = items[i].getAsFile();
                const reader = new FileReader();
                reader.onload = function(ev) {
                    const img = new Image();
                    img.onload = function() {
                        canvas.width = img.width;
                        canvas.height = img.height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0);
                        canvas.style.display = 'block';
                        zone.innerHTML = '✅ <strong>Capture d\'écran collée !</strong> Posez votre question ci-dessous.';
                        zone.style.background = '#E8F8F5';
                        zone.style.borderColor = '#00C4A7';
                        zone.style.color = '#00C4A7';
                        // Envoyer l'image à Streamlit via une iframe hack
                        const dataUrl = canvas.toDataURL('image/png');
                        window.parent.postMessage({type: 'paste_image', data: dataUrl}, '*');
                    };
                    img.src = ev.target.result;
                };
                reader.readAsDataURL(blob);
                break;
            }
        }
    });
})();
</script>
"""

# ─── Initialisation des composants (cached) ───────────────────────────────────

@st.cache_resource(show_spinner="⚙️ Initialisation de l'index RAG...")
def load_rag_engine() -> AkuiteoRAGEngine:
    engine = AkuiteoRAGEngine()
    engine.build_index(force_rebuild=False)
    return engine


@st.cache_resource
def load_vision_engine() -> AkuiteoVisionEngine:
    return AkuiteoVisionEngine()


def get_agent() -> AkuiteoAgent:
    if "agent" not in st.session_state:
        rag = load_rag_engine()
        vision = load_vision_engine()
        st.session_state["agent"] = AkuiteoAgent(rag, vision)
    return st.session_state["agent"]


def generate_ticket_content(conversation_history: list, image_attached: bool) -> str:
    """Génère le contenu d'un ticket ServiceNow pour Akuiteo."""
    now = datetime.datetime.now()
    # Extraire la dernière question utilisateur comme titre
    last_user_msg = next(
        (msg["content"] for msg in reversed(conversation_history) if msg["role"] == "user"),
        "Problème Akuiteo"
    )
    short_title = last_user_msg[:80].replace("\n", " ").strip()

    lines = [
        "# 🎫 Ticket ServiceNow — Support Akuiteo",
        "",
        "## Informations du ticket",
        "",
        f"| Champ | Valeur |",
        f"|-------|--------|",
        f"| **Numéro** | INC-{now.strftime('%Y%m%d%H%M%S')} |",
        f"| **Date d'ouverture** | {now.strftime('%d/%m/%Y %H:%M')} |",
        f"| **Catégorie** | Application métier |",
        f"| **Sous-catégorie** | Akuiteo ERP |",
        f"| **Priorité** | P3 - Normale |",
        f"| **Statut** | Nouveau |",
        f"| **Source** | Appi - Compagnon d'apprentissage |",
        f"| **Titre** | {short_title} |",
        f"| **Capture d'écran** | {'✅ Jointe' if image_attached else '❌ Non jointe'} |",
        "",
        "## Description",
        "",
        "Ticket généré automatiquement depuis Appi, le compagnon d'apprentissage Akuiteo.",
        "",
        "## Historique de conversation",
        "",
    ]
    for msg in conversation_history:
        role = "👤 Utilisateur" if msg["role"] == "user" else "🎓 Appi"
        content = msg["content"].replace("📸 *[Capture d'écran jointe]*\n\n", "")
        lines.append(f"**{role}** :")
        lines.append(f"> {content}")
        lines.append("")

    lines += [
        "---",
        "*Ticket généré par Appi - Compagnon d'apprentissage Akuiteo | Rydge Conseil*",
    ]
    return "\n".join(lines)


# ─── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown("### 🗂️ Documents indexés")
        doc_status = {
            "📘 Livre Blanc Akuiteo":    DOCUMENTS["livre_blanc"].exists(),
            "📋 Cas d'Usage CRM (POC)":  DOCUMENTS["cas_usages"].exists(),
            "📊 Mode Opératoire CRM":     DOCUMENTS["mode_op_crm"].exists(),
        }
        for name, exists in doc_status.items():
            icon = "✅" if exists else "❌"
            st.markdown(f"{icon} {name}")

        st.divider()

        if st.button("🔄 Reconstruire l'index RAG", use_container_width=True):
            with st.spinner("Reconstruction en cours..."):
                try:
                    rag = AkuiteoRAGEngine()
                    rag.build_index(force_rebuild=True)
                    load_rag_engine.clear()
                    st.session_state.pop("agent", None)
                    st.success("Index reconstruit avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")

        st.divider()

        if st.button("🗑️ Nouvelle conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state.pop("pending_feedback", None)
            st.session_state.pop("pending_ticket", None)
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
        <h2>🎓 Appi - Compagnon d'apprentissage</h2>
        <p>
            Démo : Posez vos questions et remontez vos bugs sur Akuiteo · Joignez une capture d'écran pour une analyse visuelle
        </p>
    </div>
    """, unsafe_allow_html=True)

    render_sidebar()

    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        st.error("⚠️ **ANTHROPIC_API_KEY** non configurée. Créez un fichier `.env` avec votre clé.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # ── Affichage de l'historique ──────────────────────────────────────────
    for idx, msg in enumerate(st.session_state["messages"]):
        with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🎓"):
            st.markdown(msg["content"])
            if msg.get("tools_used"):
                tools_html = ""
                for tool in msg["tools_used"]:
                    css_class = "tool-rag" if tool == "rag_search" else "tool-vision"
                    label = "📚 RAG" if tool == "rag_search" else "👁️ Vision"
                    tools_html += f'<span class="tool-badge {css_class}">{label}</span>'
                st.markdown(tools_html, unsafe_allow_html=True)

            # Feedback pour les messages assistant (sauf si déjà donné)
            if msg["role"] == "assistant" and not msg.get("feedback_given"):
                fb_key = f"feedback_{idx}"
                if st.session_state.get(fb_key) != "done":
                    st.markdown('<div class="feedback-box">💬 <strong>Cette réponse vous a-t-elle aidé ?</strong></div>', unsafe_allow_html=True)
                    col1, col2, col3 = st.columns([1, 1, 4])
                    with col1:
                        if st.button("👍", key=f"up_{idx}", help="Réponse correcte"):
                            st.session_state[fb_key] = "done"
                            st.session_state["messages"][idx]["feedback_given"] = True
                            st.session_state["pending_ticket"] = idx
                            st.rerun()
                    with col2:
                        if st.button("👎", key=f"down_{idx}", help="Réponse incorrecte"):
                            st.session_state[fb_key] = "done"
                            st.session_state["messages"][idx]["feedback_given"] = True
                            st.session_state["pending_ticket"] = idx
                            st.rerun()
                    with col3:
                        comment = st.text_input("Commentaire (optionnel)", key=f"comment_{idx}", label_visibility="collapsed", placeholder="Précisez si besoin...")
                        if comment and st.button("Envoyer", key=f"send_comment_{idx}"):
                            st.session_state[fb_key] = "done"
                            st.session_state["messages"][idx]["feedback_given"] = True
                            st.rerun()
                else:
                    st.markdown("✅ *Merci pour votre retour !*")

    # ── Proposition de création de ticket ─────────────────────────────────
    if "pending_ticket" in st.session_state:
        ticket_idx = st.session_state["pending_ticket"]
        st.markdown('<div class="ticket-box">🎫 <strong>Souhaitez-vous créer un ticket informatique ?</strong><br><small>Il contiendra votre capture d\'écran et l\'historique de conversation.</small></div>', unsafe_allow_html=True)
        col_yes, col_no = st.columns([1, 1])
        with col_yes:
            if st.button("✅ Créer le ticket", key="create_ticket"):
                image_attached = any(
                    "Capture d'écran" in msg.get("content", "")
                    for msg in st.session_state["messages"]
                )
                ticket_content = generate_ticket_content(
                    st.session_state["messages"],
                    image_attached
                )
                # Sauvegarder le ticket
                ticket_path = Path(f"ticket_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
                ticket_path.write_text(ticket_content, encoding="utf-8")
                st.session_state.pop("pending_ticket", None)
                st.success(f"✅ Ticket créé : `{ticket_path.name}`")
                st.download_button(
                    label="📥 Télécharger le ticket",
                    data=ticket_content,
                    file_name=ticket_path.name,
                    mime="text/markdown",
                )
                st.rerun()
        with col_no:
            if st.button("❌ Non merci", key="skip_ticket"):
                st.session_state.pop("pending_ticket", None)
                st.rerun()

    # ── Zone image (upload + paste) ────────────────────────────────────────
    st.markdown("---")

    # Zone copier-coller (HTML/JS)
    st.components.v1.html(PASTE_COMPONENT, height=100)

    # Upload classique en fallback
    uploaded_image = st.file_uploader(
        "📎 Ou joignez une capture d'écran",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="visible",
        help="Alternative au copier-coller",
    )

    # ── Champ de saisie ────────────────────────────────────────────────────
    user_input = st.chat_input(
        "Posez votre question sur Akuiteo... (ex: Comment créer une opportunité ?)"
    )

    # ── Traitement de la question ──────────────────────────────────────────
    if user_input:
        display_content = user_input
        if uploaded_image:
            display_content = f"📸 *[Capture d'écran jointe]*\n\n{user_input}"

        st.session_state["messages"].append({
            "role": "user",
            "content": display_content,
        })

        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(display_content)

        with st.chat_message("assistant", avatar="🎓"):
            with st.spinner("Analyse en cours..."):
                try:
                    agent = get_agent()
                    image_data = None
                    if uploaded_image:
                        uploaded_image.seek(0)
                        image_data = uploaded_image

                    result = agent.run(
                        user_message=user_input,
                        image_input=image_data,
                    )

                    response_text = result["response"]
                    tools_used = result.get("tools_used", [])
                    iterations = result.get("iterations", 1)

                    st.markdown(response_text)

                    if tools_used:
                        tools_html = ""
                        for tool in tools_used:
                            css_class = "tool-rag" if tool == "rag_search" else "tool-vision"
                            label = "📚 RAG" if tool == "rag_search" else "👁️ Vision"
                            tools_html += f'<span class="tool-badge {css_class}">{label}</span>'
                        tools_html += f'<span style="font-size:0.7rem; color:#999; margin-left:8px">({iterations} iter.)</span>'
                        st.markdown(tools_html, unsafe_allow_html=True)

                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "tools_used": tools_used,
                        "feedback_given": False,
                    })
                    st.rerun()

                except Exception as e:
                    error_msg = f"❌ Erreur de l'agent : {str(e)}"
                    st.error(error_msg)
                    logger.exception("Erreur agent")
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": error_msg,
                        "feedback_given": True,
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

    if "pending_question" in st.session_state:
        q = st.session_state.pop("pending_question")
        st.info(f"Question sélectionnée : **{q}**\n\nCopiez-la dans le champ de saisie ci-dessus.")


if __name__ == "__main__":
    main()


