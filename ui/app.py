"""
ui/app.py - Interface Streamlit pour Appi - Compagnon d'apprentissage Akuiteo
Lancer avec : streamlit run ui/app.py
"""
import sys
import logging
import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import INDEX_DIR, DOCUMENTS
from core.rag_engine import AkuiteoRAGEngine
from core.vision_engine import AkuiteoVisionEngine
from core.agent import AkuiteoAgent

# Configuration de la page
st.set_page_config(
    page_title="Appi - Compagnon Akuiteo",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CSS personnalise
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #0F4C81 0%, #00A8D6 60%, #00C4A7 100%);
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 4px 20px rgba(0,168,214,0.25);
    }
    .main-header h2 { margin:0; font-size: 1.8rem; font-weight: 700; }
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
    #paste-zone {
        border: 2px dashed #00A8D6;
        border-radius: 12px;
        padding: 28px 16px;
        text-align: center;
        color: #FFFFFF;
        font-size: 0.95rem;
        margin-bottom: 8px;
        background: rgba(0, 168, 214, 0.18);
        cursor: pointer;
        transition: all 0.2s;
        font-family: sans-serif;
    }
    #paste-zone.active {
        background: rgba(0, 196, 167, 0.25);
        border-color: #00C4A7;
    }
    #paste-preview {
        display: none;
        max-width: 100%;
        border-radius: 8px;
        margin-top: 8px;
        border: 1px solid #00C4A7;
    }
</style>
""", unsafe_allow_html=True)

# Composant copier-coller image
PASTE_COMPONENT = """
<div id="paste-zone" tabindex="0">
    <strong style="font-size:1.1rem; display:block; margin-bottom:6px">
        Zone de collage &mdash; Ctrl+V
    </strong>
    <span style="opacity:0.85; font-size:0.85rem">
        Copiez une capture d&apos;ecran Akuiteo, cliquez ici, puis faites Ctrl+V
    </span>
</div>
<img id="paste-preview" alt="Capture collee" />
<script>
(function() {
    var zone = document.getElementById("paste-zone");
    var preview = document.getElementById("paste-preview");

    zone.addEventListener("focus", function() {
        zone.style.outline = "2px solid #00C4A7";
    });
    zone.addEventListener("blur", function() {
        zone.style.outline = "none";
    });

    document.addEventListener("paste", function(e) {
        var items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (var i = 0; i < items.length; i++) {
            if (items[i].type.indexOf("image") !== -1) {
                var blob = items[i].getAsFile();
                var reader = new FileReader();
                reader.onload = function(ev) {
                    preview.src = ev.target.result;
                    preview.style.display = "block";
                    zone.innerHTML = "<strong style='font-size:1rem; color:#00C4A7'>Capture collee avec succes !</strong><br><span style='font-size:0.8rem; opacity:0.8'>Pour changer, collez une nouvelle image</span>";
                    zone.classList.add("active");
                };
                reader.readAsDataURL(blob);
                break;
            }
        }
    });
})();
</script>
"""


@st.cache_resource(show_spinner="Initialisation de l index RAG...")
def load_rag_engine():
    engine = AkuiteoRAGEngine()
    engine.build_index(force_rebuild=False)
    return engine


@st.cache_resource
def load_vision_engine():
    return AkuiteoVisionEngine()


def get_agent():
    if "agent" not in st.session_state:
        rag = load_rag_engine()
        vision = load_vision_engine()
        st.session_state["agent"] = AkuiteoAgent(rag, vision)
    return st.session_state["agent"]


def generate_ticket_content(conversation_history, image_attached):
    now = datetime.datetime.now()
    last_user_msg = next(
        (msg["content"] for msg in reversed(conversation_history) if msg["role"] == "user"),
        "Probleme Akuiteo"
    )
    short_title = last_user_msg[:80].replace("\n", " ").strip()

    lines = [
        "# Ticket ServiceNow - Support Akuiteo",
        "",
        "## Informations du ticket",
        "",
        "| Champ | Valeur |",
        "|-------|--------|",
        "| **Numero** | INC-" + now.strftime("%Y%m%d%H%M%S") + " |",
        "| **Date** | " + now.strftime("%d/%m/%Y %H:%M") + " |",
        "| **Categorie** | Application metier |",
        "| **Sous-categorie** | Akuiteo ERP |",
        "| **Priorite** | P3 - Normale |",
        "| **Statut** | Nouveau |",
        "| **Source** | Appi - Compagnon d'apprentissage |",
        "| **Titre** | " + short_title + " |",
        "| **Capture** | " + ("Jointe" if image_attached else "Non jointe") + " |",
        "",
        "## Historique de conversation",
        "",
    ]
    for msg in conversation_history:
        role = "Utilisateur" if msg["role"] == "user" else "Appi"
        content = msg["content"].replace("[Capture d'ecran jointe]", "[capture]")
        lines.append("**" + role + "** :")
        lines.append("> " + content.replace("\n", " "))
        lines.append("")
    lines.append("---")
    lines.append("*Genere par Appi - Compagnon d'apprentissage Akuiteo | Rydge Conseil*")
    return "\n".join(lines)


def render_sidebar():
    with st.sidebar:
        st.markdown("### Documents indexes")
        doc_status = {
            "Livre Blanc Akuiteo":   DOCUMENTS["livre_blanc"].exists(),
            "Cas d'Usage CRM (POC)": DOCUMENTS["cas_usages"].exists(),
            "Mode Operatoire CRM":   DOCUMENTS["mode_op_crm"].exists(),
        }
        for name, exists in doc_status.items():
            icon = "OK" if exists else "MANQUANT"
            st.markdown(f"{'✅' if exists else '❌'} {name}")

        st.divider()

        if st.button("Reconstruire l'index RAG", use_container_width=True):
            with st.spinner("Reconstruction en cours..."):
                try:
                    rag = AkuiteoRAGEngine()
                    rag.build_index(force_rebuild=True)
                    load_rag_engine.clear()
                    st.session_state.pop("agent", None)
                    st.success("Index reconstruit !")
                    st.rerun()
                except Exception as e:
                    st.error("Erreur : " + str(e))

        st.divider()

        if st.button("Nouvelle conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state.pop("pending_ticket", None)
            if "agent" in st.session_state:
                st.session_state["agent"].reset_conversation()
            st.rerun()

        st.divider()
        st.markdown("**Stack technique**")
        st.markdown("LLM : Claude API | RAG : LlamaIndex | Vision : Claude multimodal | UI : Streamlit")


def main():
    st.markdown("""
    <div class="main-header">
        <h2>Appi - Compagnon d&#39;apprentissage</h2>
        <p>Demo : Posez vos questions et remontez vos bugs sur Akuiteo &middot; Joignez une capture d&#39;ecran pour une analyse visuelle</p>
    </div>
    """, unsafe_allow_html=True)

    render_sidebar()

    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        st.error("ANTHROPIC_API_KEY non configuree.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Affichage historique
    for idx, msg in enumerate(st.session_state["messages"]):
        avatar = "U" if msg["role"] == "user" else "A"
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tools_used"):
                tools_html = ""
                for tool in msg["tools_used"]:
                    css_class = "tool-rag" if tool == "rag_search" else "tool-vision"
                    label = "RAG" if tool == "rag_search" else "Vision"
                    tools_html += '<span class="tool-badge ' + css_class + '">' + label + '</span>'
                st.markdown(tools_html, unsafe_allow_html=True)

            # Feedback
            if msg["role"] == "assistant" and not msg.get("feedback_given"):
                fb_key = "feedback_" + str(idx)
                if st.session_state.get(fb_key) != "done":
                    st.markdown('<div class="feedback-box"><strong>Cette reponse vous a-t-elle aide ?</strong></div>', unsafe_allow_html=True)
                    col1, col2, col3 = st.columns([1, 1, 4])
                    with col1:
                        if st.button("👍", key="up_" + str(idx)):
                            st.session_state[fb_key] = "done"
                            st.session_state["messages"][idx]["feedback_given"] = True
                            st.session_state["pending_ticket"] = idx
                            st.rerun()
                    with col2:
                        if st.button("👎", key="down_" + str(idx)):
                            st.session_state[fb_key] = "done"
                            st.session_state["messages"][idx]["feedback_given"] = True
                            st.session_state["pending_ticket"] = idx
                            st.rerun()
                    with col3:
                        comment = st.text_input("Commentaire", key="comment_" + str(idx), label_visibility="collapsed", placeholder="Precisez si besoin...")
                        if comment and st.button("Envoyer", key="send_" + str(idx)):
                            st.session_state[fb_key] = "done"
                            st.session_state["messages"][idx]["feedback_given"] = True
                            st.rerun()
                else:
                    st.markdown("✅ Merci pour votre retour !")

    # Proposition ticket ServiceNow
    if "pending_ticket" in st.session_state:
        st.markdown('<div class="ticket-box"><strong>Souhaitez-vous creer un ticket ServiceNow ?</strong><br><small>Il contiendra l\'historique de conversation.</small></div>', unsafe_allow_html=True)
        col_yes, col_no = st.columns([1, 1])
        with col_yes:
            if st.button("Creer le ticket", key="create_ticket"):
                image_attached = any("capture" in msg.get("content", "").lower() for msg in st.session_state["messages"])
                ticket_content = generate_ticket_content(st.session_state["messages"], image_attached)
                filename = "ticket_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".md"
                st.session_state.pop("pending_ticket", None)
                st.success("Ticket pret au telechargement !")
                st.download_button(
                    label="Telecharger le ticket",
                    data=ticket_content,
                    file_name=filename,
                    mime="text/markdown",
                )
        with col_no:
            if st.button("Non merci", key="skip_ticket"):
                st.session_state.pop("pending_ticket", None)
                st.rerun()

    # Zone paste
    st.markdown("---")
    st.components.v1.html(PASTE_COMPONENT, height=120)

    uploaded_image = st.file_uploader(
        "Ou joignez une capture d'ecran",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="visible",
    )

    user_input = st.chat_input("Posez votre question sur Akuiteo...")

    if user_input:
        display_content = user_input
        if uploaded_image:
            display_content = "[Capture jointe] " + user_input

        st.session_state["messages"].append({"role": "user", "content": display_content})

        with st.chat_message("user"):
            st.markdown(display_content)

        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                try:
                    agent = get_agent()
                    image_data = None
                    if uploaded_image:
                        uploaded_image.seek(0)
                        image_data = uploaded_image

                    result = agent.run(user_message=user_input, image_input=image_data)
                    response_text = result["response"]
                    tools_used = result.get("tools_used", [])

                    st.markdown(response_text)

                    if tools_used:
                        tools_html = ""
                        for tool in tools_used:
                            css_class = "tool-rag" if tool == "rag_search" else "tool-vision"
                            label = "RAG" if tool == "rag_search" else "Vision"
                            tools_html += '<span class="tool-badge ' + css_class + '">' + label + '</span>'
                        st.markdown(tools_html, unsafe_allow_html=True)

                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": response_text,
                        "tools_used": tools_used,
                        "feedback_given": False,
                    })
                    st.rerun()

                except Exception as e:
                    error_msg = "Erreur : " + str(e)
                    st.error(error_msg)
                    st.session_state["messages"].append({
                        "role": "assistant",
                        "content": error_msg,
                        "feedback_given": True,
                    })

    # Questions suggerees
    if not st.session_state["messages"]:
        st.markdown("---")
        st.markdown("**Questions suggerees :**")
        suggestions = [
            "Comment creer une opportunite dans le CRM ?",
            "Qu'est-ce qu'un Portefeuille dans Akuiteo ?",
            "Comment deplacer une opportunite dans le KANBAN ?",
            "A quoi servent les pictogrammes rouge, vert et orange ?",
            "Comment rechercher un compte avec des caracteres joker ?",
        ]
        cols = st.columns(len(suggestions))
        for i, (col, suggestion) in enumerate(zip(cols, suggestions)):
            with col:
                if st.button(suggestion, key="sug_" + str(i), use_container_width=True):
                    st.session_state["pending_question"] = suggestion
                    st.rerun()

    if "pending_question" in st.session_state:
        q = st.session_state.pop("pending_question")
        st.info("Question selectionnee : **" + q + "** - Copiez-la dans le champ ci-dessus.")


if __name__ == "__main__":
    main()
