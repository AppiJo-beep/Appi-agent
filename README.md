# 🤖 Agent Multimodal Akuiteo — Rydge Conseil

Assistant conversationnel basé sur Claude (Anthropic) pour faciliter l'adoption du CRM Akuiteo par les collaborateurs.

## Architecture

```
akuiteo_agent/
├── config.py                  # Configuration centralisée
├── requirements.txt           # Dépendances Python
├── setup_and_test.py          # Script de vérification
│
├── core/
│   ├── rag_engine.py          # Indexation + retrieval LlamaIndex
│   ├── vision_engine.py       # Analyse captures d'écran (Claude Vision)
│   └── agent.py               # Agent ReAct (tool_use API Claude)
│
├── ui/
│   └── app.py                 # Interface Streamlit
│
└── data/
    ├── Extrait_LivreBlanc.docx           # Procédures complètes Akuiteo
    ├── Cas_d_Usages_CRM_Akuiteo_POC.pdf  # Cas d'usage CRM avec captures UI
    ├── Mode_operatoire_-_CRM.pdf         # Mode Opératoire CRM (KPMG)
    └── index/                            # Index vectoriel (généré automatiquement)
```

## Stack

| Composant | Technologie |
|-----------|-------------|
| LLM + Vision | Claude API (`claude-opus-4-6`) |
| RAG | LlamaIndex 0.11+ |
| Embeddings | `BAAI/bge-m3` (local, gratuit, multilingue FR/EN) |
| Agent | ReAct via Claude `tool_use` |
| UI | Streamlit |

## Installation

```bash
# 1. Cloner / copier le projet
cd akuiteo_agent

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer la clé API
echo "ANTHROPIC_API_KEY=sk-ant-votre-cle" > .env

# 4. Placer les documents dans data/
#    - Extrait_LivreBlanc.docx
#    - Cas_d_Usages_CRM_Akuiteo_POC.pdf
#    - Mode_operatoire_-_CRM.pdf

# 5. Vérifier l'installation
python setup_and_test.py

# 6. Lancer l'interface
streamlit run ui/app.py
```

## Fonctionnement de l'agent

### ReAct Loop (Reason + Act)

```
User Question
     ↓
Claude analyse → choisit le(s) tool(s)
     ↓
[Tool 1] rag_search    → LlamaIndex → passages documentaires
[Tool 2] vision_analysis → Claude Vision → analyse capture d'écran
     ↓
Claude synthétise les résultats
     ↓
Réponse finale avec sources citées
```

### Tool `rag_search`
- Recherche vectorielle dans les 3 documents indexés
- Retourne les 5 passages les plus pertinents avec score de similarité
- Embed : `BAAI/bge-m3` (512 tokens/chunk, overlap 64)

### Tool `vision_analysis`
- Analyse une capture d'écran Akuiteo via Claude Vision
- Identifie : module, menu, éléments UI, état, actions possibles
- Peut être enrichi avec du contexte RAG

## Utilisation

### Questions textuelles
```
"Comment créer une opportunité ?"
"Qu'est-ce que le KANBAN dans le CRM Akuiteo ?"
"Comment utiliser les caractères joker dans la recherche de comptes ?"
```

### Questions avec capture d'écran
1. Cliquez sur 📎 (bouton d'upload)
2. Joignez votre capture d'écran Akuiteo
3. Posez votre question
```
"Je vois cet écran, que dois-je faire pour avancer mon opportunité ?"
"Pourquoi mon picto est-il rouge sur cette tuile ?"
```

## Notes techniques

- L'index vectoriel est persisté dans `data/index/` après le premier build
- Le rebuild est possible via le bouton dans la sidebar Streamlit
- L'historique de conversation est maintenu dans le session state Streamlit
- Les images sont redimensionnées automatiquement si > 4.5 MB
