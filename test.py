import asyncio
from agentic_rag_core import VectorStoreManager
from agentic_rag_core import DocumentProcessor, AgenticRAGGenerator

async def test_documents():
    processor = DocumentProcessor()
    docs = await processor.load_documents("documents")
    chunks = processor.chunk_documents(docs)

    print(f"Pages loaded: {len(docs)}")
    print(f"Chunks created: {len(chunks)}")

    # Inspect one chunk
    sample = chunks[0]
    print("\nSample chunk metadata:")
    print(sample.metadata)
    print("\nSample chunk content (first 300 chars):")
    print(sample.page_content[:300])

asyncio.run(test_documents())

vectorstore_manager = VectorStoreManager()

vectorstore_manager.load_vectorstore()

query = "How is VAT revenue shared among states?"

results = vectorstore_manager.search(query, top_k=3)

for i, r in enumerate(results["results"], 1):
    print(f"\nResult {i}")
    print("Act:", r["metadata"].get("act_name"))
    print("Page:", r["metadata"].get("page_number"))
    print("Score:", r["score"])
    print(r["text"][:300])

rag_generator = AgenticRAGGenerator(vectorstore_manager)

response = rag_generator.query(
    "how much will i pay for task as a small business owner",
    thread_id="test_session_1"
)

print(response["answer"])