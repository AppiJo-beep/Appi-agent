"""
core/rag_engine.py — Indexation et retrieval RAG avec LlamaIndex
"""
import logging
from pathlib import Path
from typing import Optional, List

from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
    Document,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.readers.file import DocxReader, PDFReader

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    CHUNK_SIZE, CHUNK_OVERLAP, TOP_K,
    INDEX_DIR, DOCUMENTS, EMBED_MODEL
)

logger = logging.getLogger(__name__)


class AkuiteoRAGEngine:
    """
    Moteur RAG pour la documentation Akuiteo.
    - Indexe les 3 documents (DOCX + PDF)
    - Expose une méthode query() pour le tool RAG de l'agent ReAct
    """

    def __init__(self):
        self.index: Optional[VectorStoreIndex] = None
        self._configure_settings()

    def _configure_settings(self):
        """Configure le modèle d'embedding local (pas de coût API)."""
        Settings.embed_model = HuggingFaceEmbedding(
            model_name=EMBED_MODEL,
            cache_folder=str(INDEX_DIR / "embed_cache"),
        )
        Settings.llm = None  # LLM géré par l'agent, pas par LlamaIndex
        Settings.chunk_size = CHUNK_SIZE
        Settings.chunk_overlap = CHUNK_OVERLAP

    def build_index(self, force_rebuild: bool = False) -> VectorStoreIndex:
        """
        Construit ou charge l'index vectoriel depuis les documents.
        Priorité au cache ; rebuild si force_rebuild=True.
        """
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        persist_path = INDEX_DIR / "vectorstore"

        # Chargement depuis cache si disponible
        if not force_rebuild and (persist_path / "docstore.json").exists():
            logger.info("⚡ Chargement de l'index depuis le cache...")
            storage_context = StorageContext.from_defaults(
                persist_dir=str(persist_path)
            )
            self.index = load_index_from_storage(storage_context)
            logger.info("✅ Index chargé depuis le cache.")
            return self.index

        # Construction de l'index
        logger.info("🔨 Construction de l'index RAG...")
        documents = self._load_documents()

        if not documents:
            raise ValueError(
                "Aucun document trouvé dans data/. "
                "Placez Extrait_LivreBlanc.docx, Cas_d_Usages_CRM_Akuiteo_POC.pdf "
                "et Mode_operatoire_-_CRM.pdf dans le dossier data/."
            )

        splitter = SentenceSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        self.index = VectorStoreIndex.from_documents(
            documents,
            transformations=[splitter],
            show_progress=True,
        )
        self.index.storage_context.persist(persist_dir=str(persist_path))
        logger.info(
            f"✅ Index construit et sauvegardé "
            f"({len(documents)} chunks depuis {len(DOCUMENTS)} documents)."
        )
        return self.index

    def _load_documents(self) -> List[Document]:
        """Charge les documents DOCX et PDF avec métadonnées source."""
        all_docs = []
        readers = {
            ".docx": DocxReader(),
            ".pdf":  PDFReader(),
        }

        # Mapping lisible pour les citations
        source_labels = {
            "livre_blanc":  "Livre Blanc Akuiteo",
            "cas_usages":   "Cas d'Usage CRM (POC)",
            "mode_op_crm":  "Mode Opératoire CRM",
        }

        for doc_key, doc_path in DOCUMENTS.items():
            if not doc_path.exists():
                logger.warning(f"⚠️  Document manquant : {doc_path.name}")
                continue

            suffix = doc_path.suffix.lower()
            reader = readers.get(suffix)
            if reader is None:
                logger.warning(f"⚠️  Format non supporté : {suffix}")
                continue

            try:
                docs = reader.load_data(file=doc_path)
                label = source_labels.get(doc_key, doc_path.name)
                for doc in docs:
                    doc.metadata["source"] = label
                    doc.metadata["filename"] = doc_path.name
                    doc.metadata["doc_key"] = doc_key
                all_docs.extend(docs)
                logger.info(f"✅ {label} : {len(docs)} chunks chargés")
            except Exception as e:
                logger.error(f"❌ Erreur chargement {doc_path.name}: {e}")

        return all_docs

    def query(self, question: str, top_k: int = TOP_K) -> dict:
        """
        Recherche RAG — appelé par le tool 'rag_search' de l'agent.

        Args:
            question : Question en langage naturel
            top_k    : Nombre de passages à récupérer

        Returns:
            dict avec clés 'passages' (list[str]) et 'sources' (list[str])
        """
        if self.index is None:
            raise RuntimeError(
                "Index non initialisé. Appelez build_index() d'abord."
            )

        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(question)

        passages = []
        sources = []
        for node in nodes:
            text = node.node.get_content().strip()
            source = node.node.metadata.get("source", "Source inconnue")
            score = round(node.score, 3) if node.score else "N/A"
            if text:
                passages.append(text)
                sources.append(f"{source} (score: {score})")

        return {
            "passages": passages,
            "sources": sources,
            "count": len(passages),
        }
