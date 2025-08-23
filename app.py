import os
import uuid
import sqlite3
from datetime import datetime
from typing import List, Optional

import pandas as pd
import streamlit as st
from PIL import Image, ImageOps
from langdetect import detect, DetectorFactory

# ---------- App Config ----------
st.set_page_config(
    page_title="Festival Memory Wall",
    page_icon="🎉",
    layout="wide",
    initial_sidebar_state="expanded",
)
DetectorFactory.seed = 0  # deterministic langdetect

# ---------- Paths ----------
DATA_DIR = os.environ.get("DATA_DIR", "data")
IMG_DIR = os.path.join("assets", "images")
DB_PATH = os.path.join(DATA_DIR, "submissions.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

# ---------- Style (simple, clean) ----------
CARD_CSS = """
<style>
    .memory-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.05);
        margin-bottom: 16px;
        border: 1px solid rgba(0,0,0,0.05);
    }
    .meta {
        color: #6b7280; /* gray-500 */
        font-size: 0.9rem;
        margin-top: 4px;
    }
    .desc {
        font-size: 0.98rem;
        line-height: 1.4;
        margin-top: 8px;
    }
    .pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        background: #f3f4f6; /* gray-100 */
        font-size: 0.85rem;
        margin-right: 6px;
        margin-top: 6px;
    }
    .footer-note {
        color: #9ca3af; /* gray-400 */
        font-size: 0.85rem;
    }
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

# ---------- DB ----------
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              image_path TEXT NOT NULL,
              description TEXT NOT NULL,
              festival TEXT,
              region TEXT,
              language TEXT,            -- user-provided
              detected_language TEXT,   -- AI detected
              year INTEGER,
              created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_filters ON submissions(festival, region, language, year);"
        )

init_db()

# ---------- Helpers ----------
def compress_and_save(image_file, dest_dir=IMG_DIR, max_w=1280, quality=85) -> str:
    """Save image as optimized JPEG and return relative path."""
    img = Image.open(image_file).convert("RGB")
    img = ImageOps.exif_transpose(img)  # auto-rotate

    w, h = img.size
    if w > max_w:
        new_h = int(h * (max_w / w))
        img = img.resize((max_w, new_h))

    uid = uuid.uuid4().hex
    dest_path = os.path.join(dest_dir, f"{uid}.jpg")
    img.save(dest_path, format="JPEG", quality=quality, optimize=True)
    return dest_path

def insert_submission(rec: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO submissions(image_path, description, festival, region,
                                    language, detected_language, year)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rec["image_path"], rec["description"], rec.get("festival"), rec.get("region"),
                rec.get("language"), rec.get("detected_language"), rec.get("year"),
            ),
        )

@st.cache_data(show_spinner=False)
def list_distinct(column: str) -> List[str]:
    with get_conn() as conn:
        df = pd.read_sql_query(
            f"""
             SELECT DISTINCT {column} AS v
             FROM submissions
             WHERE {column} IS NOT NULL AND {column} <> ''
             ORDER BY 1
            """,
            conn,
        )
    return [str(x) for x in df["v"].tolist()]

def query_submissions(
    festival: Optional[str], region: Optional[str], language: Optional[str],
    year: Optional[str], keyword: Optional[str], limit: int = 1000, offset: int = 0
) -> pd.DataFrame:
    sql = "SELECT * FROM submissions WHERE 1=1"
    args: List = []

    def add_clause(cond, *vals):
        nonlocal sql, args
        sql += f" AND {cond}"
        args.extend(vals)

    if festival and festival != "All":
        add_clause("festival = ?", festival)
    if region and region != "All":
        add_clause("region = ?", region)
    if language and language != "All":
        add_clause("(language = ? OR detected_language = ?)", language, language)
    if year and year != "All":
        add_clause("year = ?", int(year))
    if keyword:
        like = f"%{keyword.strip()}%"
        add_clause("(description LIKE ? OR festival LIKE ? OR region LIKE ?)", like, like, like)

    sql += " ORDER BY datetime(created_at) DESC"
    sql += " LIMIT ? OFFSET ?"
    args.extend([int(limit), int(offset)])

    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=args)

@st.cache_data(show_spinner=False)
def get_stats() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(
            """
            SELECT
              COUNT(*) AS total,
              COUNT(DISTINCT COALESCE(NULLIF(language,''), detected_language)) AS languages,
              COUNT(DISTINCT COALESCE(NULLIF(festival,''), '')) AS festivals,
              COUNT(DISTINCT COALESCE(NULLIF(region,''), '')) AS regions
            FROM submissions;
            """,
            conn,
        )

def export_csv() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM submissions ORDER BY created_at DESC", conn)

# ---------- Sidebar (Filters & Actions) ----------
with st.sidebar:
    st.header("🔎 Browse & Filter")
    f_festival = st.selectbox("Festival", ["All"] + list_distinct("festival"))
    f_region = st.selectbox("Region/State", ["All"] + list_distinct("region"))

    all_langs = sorted(set(list_distinct("language") + list_distinct("detected_language")))
    f_language = st.selectbox("Language", ["All"] + all_langs)

    years = [y for y in list_distinct("year") if y and y != "None"]
    years_sorted = [str(y) for y in sorted({int(y) for y in years})]
    f_year = st.selectbox("Year", ["All"] + list(reversed(years_sorted)))

    keyword = st.text_input("Keyword search", placeholder="e.g., kolam, laddoo, rangoli")

    st.divider()
    st.subheader("⬇️ Export")
    if st.button("Download CSV (admin)"):
        df_export = export_csv()
        st.download_button(
            "Save submissions.csv",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name="submissions.csv",
            mime="text/csv",
        )

# ---------- Header & Hero ----------
col_a, col_b = st.columns([3, 2])

with col_a:
    st.title("🎉 Festival Memory Wall")
    st.caption("Preserve festival traditions by sharing your memories in any Indian language.")

with col_b:
    stats = get_stats()
    t = int(stats.at[0, "total"]) if not stats.empty else 0
    langs = int(stats.at[0, "languages"]) if not stats.empty else 0
    fests = int(stats.at[0, "festivals"]) if not stats.empty else 0
    regs = int(stats.at[0, "regions"]) if not stats.empty else 0

# Horizontal layout for metrics
st.divider()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Memories", t)
with col2:
    st.metric("Languages", langs)
with col3:
    st.metric("Festivals", fests)
with col4:
    st.metric("Regions", regs)


st.divider()

# ---------- Tabs: Add Memory / Browse ----------
tab_add, tab_browse = st.tabs(["➕ Add Memory", "🖼️ Browse Wall"])

with tab_add:
    st.subheader("Upload Festival Memory")
    c1, c2 = st.columns([2, 3], vertical_alignment="top")
    with c1:
        image = st.file_uploader("Photo (JPG/PNG)", type=["jpg", "jpeg", "png"])
        description = st.text_area("Description (any language)", height=120, placeholder="Type your memory…")
        c1a, c1b = st.columns(2)
        with c1a:
            festival = st.text_input("Festival", placeholder="e.g., Pongal")
            region = st.text_input("Region/State", placeholder="e.g., Tamil Nadu")
        with c1b:
            this_year = datetime.now().year
            year = st.number_input("Year", min_value=1900, max_value=this_year, step=1, value=this_year)
            language = st.text_input("Language (optional)", placeholder="e.g., Tamil")
        consent = st.checkbox("I consent to my upload being part of an open dataset for cultural research.")
        submitted = st.button("Submit Memory", type="primary", use_container_width=True)

    with c2:
        st.markdown("**Guidelines**")
        st.write(
            "- Share only content you have rights to.\n"
            "- Avoid personal data or faces without consent.\n"
            "- Keep it respectful and culturally sensitive.\n"
            "- Tip: Enable your OS keyboard/IME for Indian scripts."
        )

    if submitted:
        if not consent:
            st.error("Please provide consent to proceed.")
        elif not image or not description.strip():
            st.error("Please upload a photo and add a description.")
        else:
            try:
                # Save image optimized
                saved_path = compress_and_save(image)

                # Detect language if not given
                detected_lang = None
                if description and not language.strip():
                    try:
                        detected_lang = detect(description)
                    except Exception:
                        detected_lang = None

                rec = {
                    "image_path": saved_path,
                    "description": description.strip(),
                    "festival": festival.strip(),
                    "region": region.strip(),
                    "language": language.strip(),
                    "detected_language": detected_lang,
                    "year": int(year) if year else None,
                }
                insert_submission(rec)
                st.success("Memory added! Find it in the wall.")
                st.balloons()
                # refresh caches so filters/stats update immediately
                list_distinct.clear()
                get_stats.clear()
            except Exception as e:
                st.exception(e)

with tab_browse:
    st.subheader("Memory Wall")
    # Pagination
    page_size = st.select_slider("Cards per page", options=[6, 9, 12, 15, 18, 24], value=12)
    page = st.number_input("Page", min_value=1, step=1, value=1)
    offset = (page - 1) * page_size

    df = query_submissions(f_festival, f_region, f_language, f_year, keyword, limit=page_size, offset=offset)
    if df.empty:
        st.info("No memories found. Try adjusting filters or keywords.")
    else:
        cols = st.columns(3)
        for i, row in df.iterrows():
            with cols[i % 3]:
                st.markdown('<div class="memory-card">', unsafe_allow_html=True)
                # image
                try:
                    st.image(row["image_path"], use_container_width=True)
                except Exception:
                    st.caption("(image unavailable)")

                # description
                st.markdown(f'<div class="desc">{row["description"]}</div>', unsafe_allow_html=True)

                # meta pills
                pills = []
                if row.get("festival"):
                    pills.append(f'<span class="pill">🎉 {row["festival"]}</span>')
                if row.get("region"):
                    pills.append(f'<span class="pill">📍 {row["region"]}</span>')
                if row.get("year"):
                    pills.append(f'<span class="pill">📅 {int(row["year"])}</span>')
                lang_show = row.get("language") or row.get("detected_language")
                if lang_show:
                    pills.append(f'<span class="pill">🌐 {lang_show}</span>')
                if pills:
                    st.markdown(" ".join(pills), unsafe_allow_html=True)

                # timestamp
                ts = row.get("created_at") or ""
                st.markdown(f'<div class="meta">Added on {ts}</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

st.divider()
st.markdown('<p class="footer-note">Built with ❤️ to preserve cultural heritage. MIT Licensed.</p>', unsafe_allow_html=True)
