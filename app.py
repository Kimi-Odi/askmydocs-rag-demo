import io
import os

import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader

from rag_pipeline import (
    build_docs_from_text,
    build_vector_store,
    build_qa_chain,
    save_vector_store,
    load_vector_store,
    get_docs_stats_from_vector_store,
    get_source_names,
    semantic_search,
    summarize_text,
    compare_two_sources,
)

load_dotenv()  # 載入 .env 裡的 OPENAI_API_KEY

st.set_page_config(
    page_title="AskMyDocs — AI Document Explorer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ========= 初始化 Session State =========

if "vector_store" not in st.session_state:
    st.session_state.vector_store = None

if "qa_chain" not in st.session_state:
    st.session_state.qa_chain = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "docs_stats" not in st.session_state:
    st.session_state.docs_stats = None

if "temperature" not in st.session_state:
    st.session_state.temperature = 0.2

if "top_k" not in st.session_state:
    st.session_state.top_k = 4

if "show_sources" not in st.session_state:
    st.session_state.show_sources = True

if "persist_enabled" not in st.session_state:
    st.session_state.persist_enabled = False

if "language_mode" not in st.session_state:
    st.session_state.language_mode = "繁體中文"

if "answer_style" not in st.session_state:
    st.session_state.answer_style = "詳細說明"

if "doc_summaries" not in st.session_state:
    # { filename: summary_text }
    st.session_state.doc_summaries = {}


# ========= Sidebar：設定與工具 =========

with st.sidebar:
    st.title("⚙️ 設定")

    st.session_state.temperature = st.slider(
        "LLM 溫度 (temperature)",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.temperature,
        step=0.05,
        help="越高越有創造力，但可能比較不穩定；越低越保守。",
    )

    st.session_state.top_k = st.slider(
        "每次檢索文件數量（Top-K）",
        min_value=1,
        max_value=8,
        value=st.session_state.top_k,
        step=1,
        help="每次回答會從向量庫中取出前 K 個最相似的片段。",
    )

    st.session_state.language_mode = st.selectbox(
        "回答語言",
        ["繁體中文", "English", "中英雙語"],
        index=["繁體中文", "English", "中英雙語"].index(
            st.session_state.language_mode
        ),
    )

    st.session_state.answer_style = st.selectbox(
        "回答風格",
        ["精簡回答", "詳細說明", "條列重點", "考試解題模式"],
        index=["精簡回答", "詳細說明", "條列重點", "考試解題模式"].index(
            st.session_state.answer_style
        ),
    )

    st.session_state.show_sources = st.checkbox(
        "回答下方顯示參考來源片段 & 信心分數",
        value=st.session_state.show_sources,
    )

    st.session_state.persist_enabled = st.checkbox(
        "啟用向量庫持久化（存到本機 faiss_db）",
        value=st.session_state.persist_enabled,
        help="勾選後建立知識庫時會自動儲存，之後可直接從磁碟載入。",
    )

    st.markdown("---")

    if st.button("🧹 清空對話"):
        st.session_state.messages = []
        st.success("對話已清空。")

    if st.button("🗑️ 清空向量庫"):
        st.session_state.vector_store = None
        st.session_state.qa_chain = None
        st.session_state.docs_stats = None
        st.session_state.doc_summaries = {}
        st.success("向量庫已清空。")

    if st.button("💾 從磁碟載入向量庫 (faiss_db)"):
        try:
            vector_store = load_vector_store("faiss_db")
            st.session_state.vector_store = vector_store
            st.session_state.qa_chain = build_qa_chain(
                vector_store,
                k=st.session_state.top_k,
                temperature=st.session_state.temperature,
            )
            st.session_state.docs_stats = get_docs_stats_from_vector_store(
                vector_store
            )
            st.success("已從 faiss_db 成功載入向量庫！")
        except Exception as e:
            st.error(f"載入失敗：{e}")

    # 下載對話紀錄
    if st.session_state.messages:
        md_lines = []
        for m in st.session_state.messages:
            role = "使用者" if m["role"] == "user" else "AI"
            md_lines.append(f"### {role}\n\n{m['content']}\n")
        md_text = "\n".join(md_lines)
        st.download_button(
            "💾 下載對話紀錄 (Markdown)",
            data=md_text,
            file_name="askmydocs_chat.md",
            mime="text/markdown",
        )


# ========= Main 區：標題與說明 =========

st.markdown(
    """
    <style>
    /* 整體背景：淡淡的藍色科技感 */
    .stApp {
        background: radial-gradient(circle at top, #e0f2fe 0, #f9fafb 45%, #f3f4f6 100%);
    }

    /* 主標題卡片 */
    .main-header {
        padding: 1.8rem 1rem 1.2rem 1rem;
        border-radius: 18px;
        background: linear-gradient(135deg, #0f4c81 0%, #3a8dde 50%, #6fd3ff 100%);
        color: white;
        text-align: center;
        margin-bottom: 1.2rem;
        box-shadow: 0 12px 30px rgba(10, 40, 80, 0.25);
    }

    .main-header-title {
        font-size: 2rem;
        font-weight: 800;
        margin: 0 0 0.3rem 0;
        letter-spacing: 0.03em;
    }

    .main-header-title span.brand {
        opacity: 0.95;
    }

    .main-header-subtitle {
        font-size: 1rem;
        margin: 0;
        opacity: 0.95;
    }

    .main-header-badge {
        display: inline-block;
        margin-top: 0.7rem;
        padding: 0.25rem 0.85rem;
        border-radius: 999px;
        background: rgba(255,255,255,0.16);
        font-size: 0.85rem;
        backdrop-filter: blur(6px);
    }
    </style>

    <div class="main-header">
        <!-- Logo 區塊：用 emoji 當簡單 Logo -->
        <div class="main-header-title">
            🔍 <span class="brand">AskMyDocs — AI Document Explorer</span>
        </div>
        <p class="main-header-subtitle">
            Upload · Search · Understand &nbsp; | &nbsp; Powered by Retrieval-Augmented Generation
        </p>
        <div class="main-header-badge">
            Multi-file RAG · Vector DB · Source Highlight · Persistent Knowledge Base
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write(
    "上傳一個或多個 PDF / TXT 檔案，系統會為你的文件建立向量化知識庫，"
    "之後你可以像問人一樣，直接用自然語言向文件提問。"
)



# ========= 檔案上傳與向量庫建立 =========

uploaded_files = st.file_uploader(
    "上傳一個或多個 PDF / TXT 檔案",
    type=["pdf", "txt"],
    accept_multiple_files=True,
)

if uploaded_files and st.button("📚 建立 / 更新知識庫"):
    all_docs = []
    doc_summaries = {}

    # 決定摘要語言（轉成 'zh' / 'en' / 'bi'）
    lang_code = {
        "繁體中文": "zh",
        "English": "en",
        "中英雙語": "bi",
    }.get(st.session_state.language_mode, "zh")

    for f in uploaded_files:
        file_bytes = f.read()
        text = ""

        if f.type == "application/pdf":
            try:
                pdf_reader = PdfReader(io.BytesIO(file_bytes))
                for page in pdf_reader.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
            except Exception as e:
                st.error(f"讀取 PDF 檔案 {f.name} 失敗：{e}")
                continue
        elif f.type == "text/plain":
            try:
                text = file_bytes.decode("utf-8", errors="ignore")
            except Exception as e:
                st.error(f"讀取文字檔 {f.name} 失敗：{e}")
                continue

        if not text.strip():
            st.warning(f"檔案 {f.name} 看起來沒有可讀取的文字內容，已略過。")
            continue

        # 每個檔案的 chunk
        docs = build_docs_from_text(text, source_name=f.name)
        all_docs.extend(docs)

        # 自動摘要
        with st.spinner(f"正在為 {f.name} 產生摘要..."):
            try:
                summary = summarize_text(text, language_mode=lang_code)
                doc_summaries[f.name] = summary
            except Exception as e:
                doc_summaries[f.name] = f"產生摘要時發生錯誤：{e}"

    if not all_docs:
        st.error("沒有成功擷取到任何文字內容，請檢查上傳的檔案。")
    else:
        with st.spinner("正在建立向量資料庫（Embedding + Indexing）..."):
            vector_store = build_vector_store(all_docs)
            st.session_state.vector_store = vector_store
            st.session_state.qa_chain = build_qa_chain(
                vector_store,
                k=st.session_state.top_k,
                temperature=st.session_state.temperature,
            )
            st.session_state.docs_stats = get_docs_stats_from_vector_store(
                vector_store
            )
            st.session_state.doc_summaries = doc_summaries

            if st.session_state.persist_enabled:
                try:
                    save_vector_store(vector_store, "faiss_db")
                    st.info("向量庫已存至本機資料夾：faiss_db")
                except Exception as e:
                    st.error(f"儲存向量庫失敗：{e}")

        st.success("✅ 知識庫建立 / 更新完成！可以開始提問。")


# ========= 文件統計資訊 & 摘要 =========

if st.session_state.docs_stats:
    stats = st.session_state.docs_stats
    st.markdown(
        f"""**目前向量庫統計：**  
- Chunk 數量：`{stats["num_docs"]}`  
- 總字元數：約 `{stats["total_chars"]}`  
- 平均每個 chunk 字元數：約 `{int(stats["avg_chars"])}`  
"""
    )

    if stats.get("per_source"):
        st.markdown("**各檔案 chunk 數量：**")
        for src, cnt in stats["per_source"].items():
            st.markdown(f"- `{src}`：{cnt} chunks")

if st.session_state.doc_summaries:
    with st.expander("📄 文件摘要（Auto Summary）"):
        for fname, summary in st.session_state.doc_summaries.items():
            st.markdown(f"### 📘 {fname}")
            st.write(summary)


st.divider()

# ========= Semantic Search & 文件比較 =========

if st.session_state.vector_store is not None:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🔎 Semantic Search（只檢索，不產生回答）")
        semantic_query = st.text_input("輸入想在文件中搜尋的內容（關鍵字或自然語言）", key="semantic_q")
        if st.button("執行搜尋", key="semantic_btn") and semantic_query:
            with st.spinner("搜尋中…"):
                try:
                    results = semantic_search(
                        st.session_state.vector_store, semantic_query, k=5
                    )
                    if not results:
                        st.info("找不到相關片段。")
                    else:
                        for i, (doc, score) in enumerate(results, start=1):
                            meta = doc.metadata or {}
                            src = meta.get("source", "unknown")
                            cid = meta.get("chunk_id", "?")
                            st.markdown(
                                f"**結果 {i}** – 檔案：`{src}`，chunk：`{cid}`，score：`{score:.4f}`"
                            )
                            st.write(doc.page_content)
                except Exception as e:
                    st.error(f"搜尋時發生錯誤：{e}")

    with col2:
        st.markdown("### 📊 文件比較（Document Compare）")
        try:
            sources = get_source_names(st.session_state.vector_store)
        except Exception as e:
            sources = []
            st.error(f"取得來源檔名失敗：{e}")

        if len(sources) >= 2:
            src_a = st.selectbox("選擇文件 A", sources, key="cmp_a")
            src_b = st.selectbox("選擇文件 B", sources, key="cmp_b", index=1)
            if st.button("比較這兩份文件", key="cmp_btn"):
                lang_code_cmp = {
                    "繁體中文": "zh",
                    "English": "en",
                    "中英雙語": "bi",
                }.get(st.session_state.language_mode, "zh")
                with st.spinner("AI 正在比較兩份文件…"):
                    try:
                        cmp_result = compare_two_sources(
                            st.session_state.vector_store,
                            src_a,
                            src_b,
                            language_mode=lang_code_cmp,
                        )
                        st.markdown("#### 📎 比較結果")
                        st.write(cmp_result)
                    except Exception as e:
                        st.error(f"比較時發生錯誤：{e}")
        else:
            st.info("目前只有一份或沒有文件，無法比較。")


st.divider()

# ========= 聊天區（RAG 問答） =========

if st.session_state.qa_chain is None:
    st.info("請先上傳檔案並建立知識庫，或從 Sidebar 載入既有向量庫。")
else:
    # 先把歷史訊息畫出來
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # 使用者輸入
    user_question = st.chat_input("請輸入你想問文件的問題…")

    if user_question:
        # 顯示使用者訊息
        st.session_state.messages.append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.write(user_question)

        # 呼叫 RAG Chain
        with st.chat_message("assistant"):
            with st.spinner("思考中…"):
                try:
                    lang_code = {
                        "繁體中文": "zh",
                        "English": "en",
                        "中英雙語": "bi",
                    }.get(st.session_state.language_mode, "zh")

                    style_code = {
                        "精簡回答": "concise",
                        "詳細說明": "detailed",
                        "條列重點": "bullets",
                        "考試解題模式": "exam",
                    }.get(st.session_state.answer_style, "detailed")

                    result = st.session_state.qa_chain(
                        {
                            "query": user_question,
                            "language_mode": lang_code,
                            "answer_style": style_code,
                        }
                    )
                    answer = result["result"]
                    sources = result.get("source_documents", [])
                    doc_scores = result.get("doc_scores", [])
                except Exception as e:
                    answer = f"回答時發生錯誤：{e}"
                    sources = []
                    doc_scores = []

                st.write(answer)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )

                # 顯示來源片段 + 信心分數
                if st.session_state.show_sources and sources:
                    with st.expander("📎 參考來源片段 & 信心分數"):
                        for i, doc in enumerate(sources, start=1):
                            meta = doc.metadata or {}
                            src = meta.get("source", "unknown")
                            cid = meta.get("chunk_id", "?")

                            score_info = ""
                            if i - 1 < len(doc_scores):
                                ds = doc_scores[i - 1]
                                score_info = (
                                    f" | score: {ds['score']:.4f} | "
                                    f"confidence: {ds['confidence']:.2f}"
                                )

                            st.markdown(
                                f"**來源 {i}** – 檔案：`{src}`，chunk：`{cid}`{score_info}"
                            )
                            st.write(doc.page_content)
                            st.caption(str(meta))
