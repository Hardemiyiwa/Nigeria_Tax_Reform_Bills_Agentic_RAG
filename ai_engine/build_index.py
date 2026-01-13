"""
Build Agentic RAG Index

This script builds the vector index from documents.
Run once before starting the API.
"""

import asyncio
from agentic_rag_core import build_agentic_rag_system


async def main():
    print("\n" + "=" * 60)
    print("BUILDING AGENTIC RAG INDEX")
    print("=" * 60 + "\n")

    documents_folder = "ai_engine\documents"

    # Build the complete Agentic RAG system
    doc_processor, vectorstore_manager, rag_generator = (
        await build_agentic_rag_system(documents_folder)
    )

    # Show stats
    stats = vectorstore_manager.get_stats()
    print("\nIndex Statistics")
    print(f"Total chunks indexed: {stats.get('total_chunks', 0)}")
    print(f"Embedding model: {stats.get('embedding_model')}")

    print("\nIndex build complete!")
    print("Next step: run `python api.py`\n")


if __name__ == "__main__":
    asyncio.run(main())
