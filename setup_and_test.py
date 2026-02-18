"""
setup_and_test.py — Script de vérification de l'installation et test minimal
Lancer depuis la racine du projet : python setup_and_test.py
"""
import sys
import os
from pathlib import Path

print("=" * 60)
print("  Agent Multimodal Akuiteo — Vérification de l'installation")
print("=" * 60)

# 1. Vérification Python
print(f"\n✅ Python {sys.version.split()[0]}")

# 2. Vérification des dépendances
deps = [
    ("anthropic",        "anthropic"),
    ("llama_index.core", "llama-index"),
    ("streamlit",        "streamlit"),
    ("PIL",              "Pillow"),
    ("dotenv",           "python-dotenv"),
]

print("\n📦 Vérification des dépendances :")
missing = []
for module, pkg in deps:
    try:
        __import__(module)
        print(f"   ✅ {pkg}")
    except ImportError:
        print(f"   ❌ {pkg} — MANQUANT")
        missing.append(pkg)

if missing:
    print(f"\n⚠️  Installez les dépendances manquantes :")
    print(f"   pip install {' '.join(missing)} --break-system-packages")
    sys.exit(1)

# 3. Vérification de la clé API
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY", "")
if api_key:
    print(f"\n✅ ANTHROPIC_API_KEY configurée ({api_key[:8]}...)")
else:
    print("\n❌ ANTHROPIC_API_KEY manquante")
    print("   Créez un fichier .env avec : ANTHROPIC_API_KEY=sk-ant-...")

# 4. Vérification des documents
from config import DOCUMENTS
print("\n📂 Vérification des documents :")
missing_docs = []
for key, path in DOCUMENTS.items():
    if path.exists():
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"   ✅ {path.name} ({size_mb:.1f} MB)")
    else:
        print(f"   ❌ {path.name} — MANQUANT dans data/")
        missing_docs.append(path.name)

if missing_docs:
    print(f"\n⚠️  Placez les fichiers manquants dans le dossier data/ :")
    for doc in missing_docs:
        print(f"   - {doc}")

# 5. Test rapide de l'embedding (si tout est OK)
if not missing and api_key and not missing_docs:
    print("\n🧪 Test rapide du moteur RAG...")
    try:
        from core.rag_engine import AkuiteoRAGEngine
        engine = AkuiteoRAGEngine()
        engine.build_index(force_rebuild=False)
        result = engine.query("Comment créer une opportunité ?", top_k=2)
        if result["passages"]:
            print(f"   ✅ RAG opérationnel — {result['count']} passages récupérés")
            print(f"   📄 Source : {result['sources'][0]}")
        else:
            print("   ⚠️  RAG initialisé mais aucun passage retourné")
    except Exception as e:
        print(f"   ❌ Erreur RAG : {e}")

print("\n" + "=" * 60)
print("  Pour lancer l'interface : streamlit run ui/app.py")
print("=" * 60)
