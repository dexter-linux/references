import concurrent.futures
import re
import urllib.parse
import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st

# ==========================================
# 1. STREAMLIT CONFIG & WARM SUNSET THEME
# ==========================================
st.set_page_config(
    page_title="RefVerify — Reference Verification Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

WARM_LIGHT_CSS = """
<style>
/* App background - Light Warm Linen & Sunset Glow */
.stApp {
    background: linear-gradient(135deg, #fdfbf7 0%, #fef5ed 50%, #f7ebe1 100%);
    color: #2c2523;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* Sidebar styling - Warm Sand Glassmorphism */
[data-testid="stSidebar"] {
    background: rgba(253, 246, 238, 0.9);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(224, 130, 93, 0.2);
}

/* Main title styling */
.warm-header {
    background: linear-gradient(90deg, #e05638 0%, #d97736 50%, #c85a32 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.8rem;
    font-weight: 800;
    margin-bottom: 0.2rem;
    letter-spacing: -1px;
}

.warm-subtitle {
    color: #7c5c4e;
    font-size: 1.05rem;
    margin-bottom: 2rem;
    font-weight: 500;
}

/* Cards & Containers */
.warm-card {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(12px);
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid rgba(224, 130, 93, 0.25);
    box-shadow: 0 8px 24px rgba(184, 115, 84, 0.08);
    margin-bottom: 1.5rem;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #e05638 0%, #d97736 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.6rem 1.8rem !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(224, 86, 56, 0.3) !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(224, 86, 56, 0.5) !important;
}

/* Inputs & Textareas */
textarea, select {
    background-color: #ffffff !important;
    color: #2c2523 !important;
    border: 1px solid #e0825d !important;
    border-radius: 10px !important;
}

/* Warm Line Divider */
.warm-line {
    height: 4px;
    background: linear-gradient(90deg, transparent, #e05638, #f0a273, transparent);
    border-radius: 2px;
    margin: 1.5rem 0;
}
</style>
"""

st.markdown(WARM_LIGHT_CSS, unsafe_allow_html=True)

# ==========================================
# 2. HELPER & SEARCH FUNCTIONS
# ==========================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}


def clean_reference(ref_text: str) -> str:
    """Clean reference text for search optimization."""
    cleaned = re.sub(
        r"^\s*\[?\d+\]?\.?\s*", "", ref_text
    )  # Remove [1], 1., etc.
    return cleaned.strip()


def check_crossref(query: str):
    """Query Crossref API for scholarly publication matches."""
    url = (
        f"https://api.crossref.org/works?query={urllib.parse.quote(query)}&rows=1"
    )
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        if response.status_code == 200:
            data = response.json()
            items = data.get("message", {}).get("items", [])
            if items:
                item = items[0]
                title = item.get("title", ["Unknown Title"])[0]
                doi = item.get("DOI", "")
                link = item.get("URL", f"https://doi.org/{doi}")
                score = item.get("score", 0)

                if score > 20:
                    return {
                        "status": "Found (Crossref)",
                        "title": title,
                        "link": link,
                        "confidence": "High" if score > 35 else "Medium",
                    }
    except Exception:
        pass
    return None


def check_duckduckgo(query: str):
    """Fallback web search using DuckDuckGo HTML parsing."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("a", class_="result__url")
            if results:
                first_link = results[0].get("href", "").strip()
                if first_link:
                    if first_link.startswith("//"):
                        first_link = "https:" + first_link
                    return {
                        "status": "Found (Web)",
                        "title": "Web Match Found",
                        "link": first_link,
                        "confidence": "Medium",
                    }
    except Exception:
        pass
    return None


def verify_reference(ref: str) -> dict:
    """Agent worker task: Verify a single reference line."""
    cleaned = clean_reference(ref)
    if not cleaned:
        return {
            "Original Reference": ref,
            "Status": "Invalid Input",
            "Matched Title / Note": "Empty line",
            "Confidence": "None",
            "Link": "",
        }

    # Step 1: Check Academic Database (Crossref)
    crossref_result = check_crossref(cleaned)
    if crossref_result:
        return {
            "Original Reference": ref,
            "Status": crossref_result["status"],
            "Matched Title / Note": crossref_result["title"],
            "Confidence": crossref_result["confidence"],
            "Link": crossref_result["link"],
        }

    # Step 2: Fallback to Web Search
    ddg_result = check_duckduckgo(cleaned)
    if ddg_result:
        return {
            "Original Reference": ref,
            "Status": ddg_result["status"],
            "Matched Title / Note": ddg_result["title"],
            "Confidence": ddg_result["confidence"],
            "Link": ddg_result["link"],
        }

    # Step 3: Not Found
    fallback_search_url = (
        f"https://scholar.google.com/scholar?q={urllib.parse.quote(cleaned)}"
    )
    return {
        "Original Reference": ref,
        "Status": "Not Verified",
        "Matched Title / Note": "No high-confidence match found",
        "Confidence": "Low",
        "Link": fallback_search_url,
    }


# ==========================================
# 3. SIDEBAR & SETTINGS
# ==========================================
with st.sidebar:
    st.markdown("## 📚 **RefVerify Agent**")
    st.markdown("---")
    st.markdown(
        "**Verification Engines:**\n"
        "• 🔬 **Crossref API** (Academic DOIs)\n"
        "• 🌐 **Web Crawler** (Publications & Publishers)\n"
        "• 🎓 **Google Scholar** (Fallback Search)"
    )
    st.markdown("---")
    st.info(
        "Paste your bibliography citations to auto-verify titles, DOIs, and direct links."
    )

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
st.markdown(
    '<div class="warm-header">📚 RefVerify Agent</div>', unsafe_allow_html=True
)
st.markdown(
    '<div class="warm-subtitle">Automated Academic Citation & Reference Verification Pipeline</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="warm-line"></div>', unsafe_allow_html=True)

default_input = """1. Vaswani, A., et al. (2017). Attention is all you need. Advances in neural information processing systems, 30.
2. LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. Nature, 521(7553), 436-444.
3. Fake Nonexistent Author (2099). Super imaginary quantum deep network paper that does not exist."""

user_input = st.text_area(
    "Paste Reference List (One citation per line):",
    height=200,
    value=default_input,
)

confirm_button = st.button("🔎 Verify References Now", type="primary")

if confirm_button:
    lines = [line.strip() for line in user_input.split("\n") if line.strip()]

    if not lines:
        st.warning("Please paste at least one reference to verify.")
    else:
        st.info(
            f"Analyzing {len(lines)} references in parallel. Searching academic databases..."
        )

        progress_bar = st.progress(0)
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_ref = {
                executor.submit(verify_reference, line): line for line in lines
            }
            completed_count = 0

            for future in concurrent.futures.as_completed(future_to_ref):
                res = future.result()
                results.append(res)
                completed_count += 1
                progress_bar.progress(completed_count / len(lines))

        ref_order = {line: i for i, line in enumerate(lines)}
        results.sort(key=lambda x: ref_order.get(x["Original Reference"], 9999))

        st.success("Verification Complete!")

        df = pd.DataFrame(results)

        st.markdown('<div class="warm-card">', unsafe_allow_html=True)
        st.subheader("📋 Verification Results")
        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn(
                    "Source Link", display_text="Open Article / Search"
                )
            },
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv_data,
            file_name="verified_references.csv",
            mime="text/csv",
        )
