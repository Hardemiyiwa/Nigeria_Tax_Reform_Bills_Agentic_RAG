"""
Agentic RAG System
"""
from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from IPython.display import Image, display, Markdown
from typing import Literal, List, Optional, TypedDict, Dict
import os
import re
from langchain_core.messages import BaseMessage
import logging

class DocumentProcessor:
    """
    Handles document loading and chunking.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        """
        Initialize the document processor.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def extract_act_metadata(self, filename: str):
        name = filename.replace(".pdf", "").strip()

        # Extract year if present
        year_match = re.search(r"(20\d{2})", name)
        year = int(year_match.group(1)) if year_match else None

        # Clean up filename into a readable title
        clean_title = (
            name.replace("_", " ")
                .replace(",", "")
                .replace("EDITED", "")
                .replace("FRIDAY", "")
                .strip()
        )

        return {
            "document_title": clean_title.title(),
            "act_name": clean_title.title(),
            "year": year,
            "document_type": "Act",
            "jurisdiction": "Nigeria",
            "source_file": filename,
        }

    async def load_documents(self, documents_folder: str) -> List:
        """
        load all documents from a folder
        """
        ALLOWED_METADATA_KEYS = {
            "document_title",
            "act_name",
            "year",
            "document_type",
            "jurisdiction",
            "source_file",
            "page_number",
        }

        pages = []

        for filename in os.listdir(documents_folder):
            if not filename.lower().endswith(".pdf"):
                continue

            file_path = os.path.join(documents_folder, filename)
            loader = PyPDFLoader(file_path)

            async for page in loader.alazy_load():
                # Build clean metadata
                metadata = self.extract_act_metadata(filename)

                # Use human-readable page number
                page_number = page.metadata.get("page_label")
                metadata["page_number"] = int(page_number) if page_number and page_number.isdigit() else None

                # Replace metadata completely (drop noisy PDF fields)
                page.metadata = {
                    k: v for k, v in metadata.items()
                    if k in ALLOWED_METADATA_KEYS
                }

                pages.append(page)

        return pages
    
    def chunk_documents(self, documents:List) -> List:
        """
        Split documents into smaller chunks.
        """
        chunks = self.text_splitter.split_documents(documents)
        print(f"Created {len(chunks)} chunks")
        return chunks


class VectorStoreManager:
    """
    Manage vector embeddings and ChromaDB storage/retrieval
    """

    def __init__(
            self,
            embedding_model: str = "text-embedding-3-small",
            persist_directory: str = "./chroma_db",
            collection_name: str = "tax_act"
    ):
        """
        Initialize the vector store manager
        """
        load_dotenv()

        self.embedding_model = embedding_model
        self.persist_directory = persist_directory
        self.collection_name = collection_name

        print(f"Loading embedding model: {embedding_model}...")
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model
        )
        print("Embedding model loaded!")

        self.vectorstore = None

    def create_vectorstore(self, chunks: List):
        """
        Create a vector store from document chunks.
        """
        print("Creating vector store with embeddings...")
        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        self.vectorstore.add_documents(documents=chunks)
        print(f"Vector store created with {len(chunks)} chunks!")

    def load_vectorstore(self):
        """
        Load an existing vector store from disk.
        """
        print("Loading existing vector store...")
        self.vectorstore = Chroma(
            collection_name=self.collection_name,
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )
        print("Vector store loaded!")

    def search(self, query: str, top_k: int = 3) -> Dict:
        """
        Search for relevant documents.(Direct similarity search (for debugging or evaluation))
        """
        if self.vectorstore is None:
            raise RuntimeError("No vector store loaded. Create or load one first.")

        results_with_scores = self.vectorstore.similarity_search_with_score(
            query, k=top_k
        )

        formatted_results = {
            "query": query,
            "results": []
        }

        for doc, score in results_with_scores:
            formatted_results["results"].append({
                "text": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score)
            })

        return formatted_results
    
    def retrieve_documents(self, query: str, k: int = 5) -> list:
        """
        Retrieve relevant legal document chunks from the Nigerian tax Acts.

        This tool should be used ONLY when policy evidence is required
        to answer a user's question.

        Args:
            query (str): A refined, legal-style search query
            k (int): Number of document chunks to retrieve

        Returns:
            list: A list of retrieved document chunks with metadata
        """

        retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": k,
                "fetch_k": 10
            }
        )

        docs = retriever.invoke(query)

        if not docs:
            return []

        results = []

        for doc in docs:
            results.append({
                "content": doc.page_content,
                "document_title": doc.metadata.get("document_title"),
                "act_name": doc.metadata.get("act_name"),
                "page_number": doc.metadata.get("page_number"),
                "year": doc.metadata.get("year"),
                "jurisdiction": doc.metadata.get("jurisdiction"),
                "source_file": doc.metadata.get("source_file")
            })

        return results
    
    def get_stats(self) -> Dict:
        """
        Get statistics about the vector store.
        """
        if self.vectorstore is None:
            return {"error": "No vector store loaded"}

        collection = self.vectorstore._collection
        return {
            "collection_name": self.collection_name,
            "total_chunks": collection.count(),
            "embedding_model": self.embedding_model
        }

    
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgenticRAGGenerator:
    """
    V1 Agentic RAG generator:
    - Single assistant node
    - Conditional retrieval
    - Conversation memory
    """

    def __init__(
        self,
        vectorstore_manager,
        openai_model: str = "gpt-4o-mini",
        temperature: float = 0.5,
    ):
        """
        Initialize the Agentic RAG system.
        """
        load_dotenv()

        self.vectorstore_manager = vectorstore_manager
        self.openai_model = openai_model
        self.temperature = temperature

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=openai_model,
            temperature=temperature,
        )
        logger.info(f"OpenAI LLM initialized ({openai_model})")

        # Tools
        self.tools = self._build_tools()
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # System Prompt
        self.system_prompt = SystemMessage(
            content="""
You are an AI assistant specialized in Nigerian tax law and public finance policy.
Your knowledge source is a collection of official Nigerian tax legislation,
including the Nigeria Tax Act 2025, Nigeria Tax Administration Act,
Nigeria Revenue Service Act, Joint Revenue Board of Nigeria (Establishment) Act,
and related government documents.

DOMAIN RESTRICTION:
Only answer questions related to:
- Nigerian tax laws and tax reforms
- VAT, income tax, and revenue administration
- Tax obligations of individuals and businesses
- Revenue allocation and derivation among federal, state, and local governments
- Institutional roles of Nigerian tax authorities

If a question is outside this domain, politely state that it is outside your scope.

RETRIEVAL DECISION RULES:

DO NOT retrieve for:
- Greetings or small talk
- Questions about your capabilities
- Simple clarifications that do not require legal citations

DO retrieve for:
- Questions about tax rates, obligations, exemptions, or penalties
- Questions involving revenue distribution or fiscal policy
- Any question where citing official Acts improves accuracy or trust

CITATION RULES:
- Use inline citations like [1], [2]
- End answers with a "Sources" section
- Each source must include Act name and page number
- Never invent citations
- If documents do not contain the answer, say so clearly

Never fabricate legal provisions or interpretations.
"""
        )

        # Build LangGraph agent ONCE
        self.agent = self._build_agent()

    def _build_tools(self):
        @tool
        def retrieve_documents(query: str, k: int = 5):
            """
            Retrieve relevant legal document chunks from Nigerian tax Acts.
            """
            return self.vectorstore_manager.retrieve_documents(query, k)

        return [retrieve_documents]

    # LangGraph Nodes
    def assistant(self, state: MessagesState) -> dict:
        """
        Assistant node:
        decides whether to retrieve or answer directly.
        """
        messages = state["messages"]

        # Inject system prompt once
        if not messages or messages[0].type != "system":
            messages = [self.system_prompt] + messages
            logger.info("System prompt injected")

        logger.info(f"User input: {messages[-1].content[:100]}")

        response = self.llm_with_tools.invoke(messages)

        if response.tool_calls:
            logger.info("Agent decided to retrieve documents")
        else:
            logger.info("Agent answering directly")

        return {"messages": [response]}

    def should_continue(
        self, state: MessagesState
    ) -> Literal["tools", "__end__"]:
        """
        Decide whether to call tools or finish.
        """
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return "__end__"

    # Graph Construction
    def _build_agent(self):
        """
        Build and compile the LangGraph agent.
        """
        builder = StateGraph(MessagesState)

        builder.add_node("assistant", self.assistant)
        builder.add_node("tools", ToolNode(self.tools))

        builder.add_edge(START, "assistant")
        builder.add_conditional_edges(
            "assistant",
            self.should_continue,
            {"tools": "tools", "__end__": END},
        )
        builder.add_edge("tools", "assistant")

        memory = MemorySaver()

        agent = builder.compile(checkpointer=memory)
        logger.info("LangGraph agent compiled successfully")

        return agent

    # Public API
    def query(self, user_input: str, thread_id: str = "default"):
        """
        Ask a question and get an answer from the agent.
        """
        result = self.agent.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config={"configurable": {"thread_id": thread_id}},
        )

        final_answer = None

        for message in result["messages"]:
            if isinstance(message, AIMessage):
                if message.content and not message.tool_calls:
                    final_answer = message.content

        return {
            "question": user_input,
            "answer": final_answer,
        }


async def build_agentic_rag_system(documents_folder: str) -> tuple:
    """
    Build a complete Agentic RAG system from documents.
    """
    print(f"\n{'='*60}")
    print("BUILDING AGENTIC RAG SYSTEM")
    print(f"{'='*60}\n")

    # Step 1: Process documents
    doc_processor = DocumentProcessor()
    documents = await doc_processor.load_documents(documents_folder)
    chunks = doc_processor.chunk_documents(documents)

    # Step 2: Vector store
    vectorstore_manager = VectorStoreManager()

    if os.path.exists(vectorstore_manager.persist_directory):
        vectorstore_manager.load_vectorstore()
    else:
        vectorstore_manager.create_vectorstore(chunks)

    # Step 3: Agentic RAG
    rag_generator = AgenticRAGGenerator(vectorstore_manager)

    print(f"\n{'='*60}")
    print("AGENTIC RAG SYSTEM READY!")
    print(f"{'='*60}\n")

    return doc_processor, vectorstore_manager, rag_generator