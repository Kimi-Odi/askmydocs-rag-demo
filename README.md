# AskMyDocs — AI Document Explorer

## Upload, Search, and Understand Your Documents with AI-Powered Retrieval-Augmented Generation (RAG)

This project provides a user-friendly interface built with Streamlit to interact with your documents using advanced AI capabilities. Upload multiple PDF or TXT files, build a searchable knowledge base, ask questions in natural language, perform semantic searches, and even compare documents – all powered by a Retrieval-Augmented Generation (RAG) pipeline.

## Features

*   **Multi-file Document Upload**: Easily upload one or more PDF or TXT files to build your knowledge base.
*   **AI-Powered Q&A**: Ask natural language questions about your uploaded documents and get accurate answers, with references to the source chunks.
*   **Semantic Search**: Perform advanced searches within your documents based on meaning, not just keywords.
*   **Automatic Document Summarization**: Get AI-generated summaries for each uploaded document.
*   **Document Comparison**: Compare two documents from your knowledge base and receive an AI-generated analysis of their similarities and differences.
*   **Persistent Knowledge Base**: Save and load your vectorized knowledge base (FAISS) to avoid re-processing documents.
*   **Customizable LLM Parameters**: Adjust parameters like LLM temperature (creativity) and Top-K (number of retrieved document chunks).
*   **Multi-language Support**: Choose your preferred answer language (Traditional Chinese, English, Bilingual).
*   **Multiple Answer Styles**: Select how the AI should answer (Concise, Detailed, Bullet Points, Exam Mode).
*   **Interactive Streamlit UI**: A clean and intuitive web interface for seamless interaction.

## How it Works (Retrieval-Augmented Generation - RAG)

The core of this application is a RAG pipeline. When you upload documents:
1.  **Document Chunking**: Documents are split into smaller, manageable pieces (chunks).
2.  **Embedding**: These chunks are converted into numerical representations (embeddings) using OpenAI's `text-embedding-3-small` model.
3.  **Vector Store**: The embeddings are stored in a FAISS vector database, enabling fast similarity searches.

When you ask a question:
1.  Your query is also converted into an embedding.
2.  The system retrieves the most semantically similar document chunks from the FAISS vector store.
3.  These relevant chunks (context) are then fed to an OpenAI Chat Model (`gpt-4o-mini`) along with your question.
4.  The LLM generates an answer based *only* on the provided context, reducing hallucinations and providing traceable answers.

## Setup and Installation

Follow these steps to get the project up and running on your local machine.

### Prerequisites

*   Python 3.8+
*   An OpenAI API Key

### Steps

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Kimi-Odi/askmydocs-rag-demo.git
    cd askmydocs-rag-demo
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your OpenAI API Key:**
    Create a file named `.env` in the root directory of the project and add your OpenAI API key:
    ```
    OPENAI_API_KEY="your_openai_api_key_here"
    ```
    **Note**: The `.env` file is included in `.gitignore` to prevent it from being committed to version control.

## Usage

To run the Streamlit application, execute the following command from the project root directory:

```bash
streamlit run app.py
```

This will open the application in your web browser, usually at `http://localhost:8501`.

### Interface Guide

*   **Sidebar**: Adjust LLM parameters (temperature, Top-K), select language and answer style, and manage your knowledge base (clear conversation/vector store, load/save vector store).
*   **File Uploader**: Upload your PDF/TXT documents.
*   **Build Knowledge Base**: Click this button after uploading files to create or update the vector store.
*   **Chat Input**: Ask questions related to your documents here.
*   **Semantic Search**: Use this section to perform raw semantic queries on your knowledge base.
*   **Document Compare**: Select two uploaded documents to get an AI-generated comparison.

Enjoy exploring your documents with AI!
