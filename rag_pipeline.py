# rag_pipeline.py

from typing import List, Dict, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.documents import Document


# ========= 文件處理 =========

def build_docs_from_text(text: str, source_name: str = "upload") -> List[Document]:
    """
    把一大段文字切成多個 Document chunk，給後面做 embedding 用。
    source_name 會放在 metadata["source"]，方便之後顯示來源檔案。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )
    chunks = splitter.split_text(text)
    docs = [
        Document(page_content=chunk, metadata={"source": source_name, "chunk_id": i})
        for i, chunk in enumerate(chunks)
    ]
    return docs


def build_vector_store(docs: List[Document]) -> FAISS:
    """
    建立向量資料庫（FAISS）
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = FAISS.from_documents(docs, embeddings)
    return vector_store


def save_vector_store(vector_store: FAISS, path: str = "faiss_db"):
    """
    把向量庫存到本地資料夾（持久化）
    """
    import os

    os.makedirs(path, exist_ok=True)
    vector_store.save_local(path)


def load_vector_store(path: str = "faiss_db") -> FAISS:
    """
    從本地資料夾載入向量庫。
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = FAISS.load_local(
        path,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    return vector_store


def get_all_docs_from_vector_store(vector_store: FAISS):
    """
    取得向量庫裡所有 Document。
    """
    if hasattr(vector_store, "docstore") and hasattr(vector_store.docstore, "_dict"):
        return vector_store.docstore._dict.values()
    raise RuntimeError("無法從 vector_store 取出文件列表（docstore 格式可能有變更）。")


def get_docs_stats_from_vector_store(vector_store: FAISS) -> Dict:
    """
    向量庫中文件統計資訊。
    """
    docs = list(get_all_docs_from_vector_store(vector_store))
    total_docs = len(docs)
    total_chars = sum(len(d.page_content) for d in docs)
    avg_chars = total_docs and total_chars / total_docs or 0
    # 每個 source 的 chunk 數
    per_source: Dict[str, int] = {}
    for d in docs:
        src = d.metadata.get("source", "unknown")
        per_source[src] = per_source.get(src, 0) + 1
    return {
        "num_docs": total_docs,
        "total_chars": total_chars,
        "avg_chars": avg_chars,
        "per_source": per_source,
    }


def get_source_names(vector_store: FAISS) -> List[str]:
    """
    取得目前向量庫中所有來源檔名。
    """
    docs = get_all_docs_from_vector_store(vector_store)
    names = sorted({d.metadata.get("source", "unknown") for d in docs})
    return names


def group_docs_by_source(vector_store: FAISS) -> Dict[str, List[Document]]:
    """
    依照 source 分組文件。
    """
    docs = get_all_docs_from_vector_store(vector_store)
    groups: Dict[str, List[Document]] = {}
    for d in docs:
        src = d.metadata.get("source", "unknown")
        groups.setdefault(src, []).append(d)
    return groups


# ========= 摘要、語意搜尋、文件比較 =========

def summarize_text(
    text: str,
    language_mode: str = "zh",
    model: str = "gpt-4o-mini",
    max_chars: int = 6000,
) -> str:
    """
    對單一檔案內容做摘要。
    language_mode: 'zh' / 'en' / 'bi'
    """
    snippet = text[:max_chars]
    llm = ChatOpenAI(model=model, temperature=0.2)

    if language_mode == "en":
        lang_inst = "Please summarize the following document in English."
    elif language_mode == "bi":
        lang_inst = (
            "請先用繁體中文寫出摘要，然後在下面附上一份英文摘要。"
        )
    else:
        lang_inst = "請用繁體中文幫我產生這份文件的摘要與重點條列。"

    prompt = f"""{lang_inst}

【文件內容】：
{snippet}
"""
    res = llm.invoke(prompt)
    return res.content if hasattr(res, "content") else str(res)


def semantic_search(
    vector_store: FAISS, query: str, k: int = 5
) -> List[Tuple[Document, float]]:
    """
    純語意搜尋（不透過 LLM 回答），回傳 (Document, score)。
    """
    results = vector_store.similarity_search_with_score(query, k=k)
    return results


def compare_two_sources(
    vector_store: FAISS,
    source_a: str,
    source_b: str,
    language_mode: str = "zh",
    model: str = "gpt-4o-mini",
    max_chars_each: int = 4000,
) -> str:
    """
    比較兩份文件的異同。
    """
    groups = group_docs_by_source(vector_store)
    docs_a = groups.get(source_a, [])
    docs_b = groups.get(source_b, [])

    text_a = "\n".join(d.page_content for d in docs_a)[:max_chars_each]
    text_b = "\n".join(d.page_content for d in docs_b)[:max_chars_each]

    llm = ChatOpenAI(model=model, temperature=0.2)

    if language_mode == "en":
        lang_inst = "Please answer in English."
    elif language_mode == "bi":
        lang_inst = "請先用繁體中文比較，再附上一份英文說明。"
    else:
        lang_inst = "請用繁體中文詳細比較。"

    prompt = f"""{lang_inst}

現在有兩份文件：

【文件 A：{source_a}】：
{text_a}

【文件 B：{source_b}】：
{text_b}

請幫我完成：
1. 說明兩份文件的主要內容差異。
2. 列出它們的共通點。
3. 如果適用，指出哪一份較完整、哪一份較適合初學者。
"""

    res = llm.invoke(prompt)
    return res.content if hasattr(res, "content") else str(res)


# ========= 簡易 RAG 問答類別 =========

class SimpleRetrievalQA:
    """
    自訂版 RetrievalQA：
    - __call__({ "query": "問題", "language_mode": "...", "answer_style": "..." })
      -> { "result": 答案字串, "source_documents": [docs], "doc_scores": [...] }

    支援參數：
    - k: 檢索前 k 個相似文件
    - temperature: LLM 溫度
    - model: OpenAI Chat 模型名稱
    """

    def __init__(
        self,
        vector_store: FAISS,
        k: int = 4,
        temperature: float = 0.2,
        model: str = "gpt-4o-mini",
    ):
        self.vector_store = vector_store
        self.k = k
        self.temperature = temperature
        self.model = model
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
        )

    def _build_language_instruction(self, language_mode: str) -> str:
        if language_mode == "en":
            return "Please answer in English."
        elif language_mode == "bi":
            return "請先用繁體中文回答，接著提供英文翻譯版本。"
        else:
            return "請用繁體中文回答。"

    def _build_style_instruction(self, answer_style: str) -> str:
        if answer_style == "concise":
            return "請盡量精簡作答，控制在數行文字內。"
        elif answer_style == "bullets":
            return "請以條列式重點整理內容，每點不宜過長。"
        elif answer_style == "exam":
            return "請用考試解題/詳解的風格說明，步驟清楚、條理分明。"
        else:
            return "請提供有條理的詳細說明，可適度分段與條列。"

    def __call__(self, inputs: dict):
        query = inputs.get("query") or inputs.get("question")
        if not query:
            raise ValueError("SimpleRetrievalQA 需要傳入 {'query': '你的問題'}")

        language_mode = inputs.get("language_mode", "zh")
        answer_style = inputs.get("answer_style", "detailed")

        # 使用 similarity_search_with_score 打出信心分數
        results = self.vector_store.similarity_search_with_score(query, k=self.k)
        docs = [doc for doc, _ in results]
        scores = [score for _, score in results]

        # 把文件內容組成 context
        context_parts = []
        doc_scores: List[Dict] = []
        if scores:
            max_s = max(scores)
            min_s = min(scores)
        else:
            max_s = min_s = 0.0

        for i, (doc, score) in enumerate(results):
            src = doc.metadata.get("source", "unknown")
            cid = doc.metadata.get("chunk_id", "?")

            # 簡單正規化成 "信心分數"：分數越小越相似
            if max_s != min_s:
                conf = 1.0 - (score - min_s) / (max_s - min_s)
            else:
                conf = 1.0
            conf = max(0.0, min(1.0, conf))

            context_parts.append(
                f"[片段 {i+1}]（來源: {src} / chunk {cid} / 信心: {conf:.2f}）\n"
                f"{doc.page_content}"
            )
            doc_scores.append(
                {
                    "rank": i + 1,
                    "source": src,
                    "chunk_id": cid,
                    "score": float(score),
                    "confidence": float(conf),
                }
            )

        context = "\n\n".join(context_parts)

        lang_inst = self._build_language_instruction(language_mode)
        style_inst = self._build_style_instruction(answer_style)

        prompt = f"""{lang_inst}
{style_inst}

你是一個閱讀使用者上傳文件的助理。請根據下列提供的文件內容，回答使用者的問題。

【文件內容】：
{context}

【問題】：
{query}

回答要求：
1. 優先根據文件中的內容作答。
2. 如文件中資訊不足，請明確說明「在文件裡找不到完整答案」，不要亂掰。
3. 如有需要，可以條列式整理重點。
"""

        res = self.llm.invoke(prompt)
        answer_text = res.content if hasattr(res, "content") else str(res)

        return {
            "result": answer_text,
            "source_documents": docs,
            "doc_scores": doc_scores,
        }


def build_qa_chain(
    vector_store: FAISS,
    k: int = 4,
    temperature: float = 0.2,
    model: str = "gpt-4o-mini",
) -> SimpleRetrievalQA:
    """
    回傳自訂的 SimpleRetrievalQA。
    """
    return SimpleRetrievalQA(
        vector_store=vector_store,
        k=k,
        temperature=temperature,
        model=model,
    )
