#!/usr/bin/env python3
"""
streamlit_app.py - SAP GitHub Repos Finder

Streamlit web UI for exploring top 25 SAP-related GitHub repositories.
Reads static sap_top25.json (updated weekly by GitHub Action).

Usage:
    streamlit run streamlit_app.py

Requirements:
    - streamlit>=1.28.0
    - pandas>=2.0.0
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


# Page configuration
st.set_page_config(
    page_title="SAP GitHub Repos Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Constants
JSON_PATH = Path(__file__).parent / "sap_top30.json"
SAP_AREAS = [
    "ABAP", "OData", "Fiori", "UI5", "Workflow",
    "RAP", "CAP", "S4 Conversion", "GenAI", "Automation", "Other"
]


@st.cache_data(ttl=3600, show_spinner="Loading repository data...")
def load_repos():
    """Load and parse sap_top30.json with caching."""
    if not JSON_PATH.exists():
        return None, "File not found: sap_top30.json. Run fetch script or wait for weekly Action."

    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"

    # Handle both old format (array) and new format (wrapper with generated_at)
    if isinstance(data, list):
        repos = data
        generated_at = datetime.fromtimestamp(JSON_PATH.stat().st_mtime).isoformat() + "Z"
    elif isinstance(data, dict) and "repos" in data:
        repos = data["repos"]
        generated_at = data.get("generated_at", datetime.fromtimestamp(JSON_PATH.stat().st_mtime).isoformat() + "Z")
    else:
        return None, "Unexpected JSON structure"

    if not repos:
        return [], generated_at

    # Convert to DataFrame for easier filtering
    df = pd.DataFrame(repos)
    return df, generated_at


def filter_repos(df: pd.DataFrame, selected_areas: list, search_query: str) -> pd.DataFrame:
    """Apply area and keyword filters."""
    if df.empty:
        return df

    filtered = df.copy()

    # Area filter
    if selected_areas and "All" not in selected_areas:
        filtered = filtered[filtered["primary_area"].isin(selected_areas)]

    # Keyword search (case-insensitive, OR across multiple fields)
    if search_query:
        query = search_query.lower().strip()
        mask = (
            filtered["skills"].apply(lambda s: any(query in skill.lower() for skill in s))
            | filtered["what_it_offers"].str.lower().str.contains(query, na=False)
            | filtered["purpose"].str.lower().str.contains(query, na=False)
            | filtered["topics"].apply(lambda t: any(query in topic.lower() for topic in t))
            | filtered["full_name"].str.lower().str.contains(query, na=False)
            | filtered["description"].str.lower().str.contains(query, na=False)
        )
        filtered = filtered[mask]

    return filtered.reset_index(drop=True)


def format_skills(skills: list) -> str:
    """Format skills list for display."""
    if not skills:
        return ""
    if len(skills) <= 5:
        return ", ".join(skills)
    return ", ".join(skills[:5]) + f" +{len(skills)-5} more"


def render_repo_card(row: pd.Series):
    """Render a single repository detail expander."""
    with st.expander(f"#{row.name + 1}  {row['full_name']}  ⭐ {row['stargazers_count']}", expanded=False):
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**Primary Area:** {row['primary_area']}")
            st.markdown(f"**What it offers:** {row['what_it_offers']}")
            st.markdown(f"**Purpose:** {row['purpose']}")

            # Topics as badges
            if row["topics"]:
                st.markdown("**Topics:**")
                topic_html = " ".join([f'<span style="background:#e1e4e8;color:#24292e;padding:2px 6px;border-radius:3px;margin:2px;font-size:0.85em;">{t}</span>' for t in row["topics"]])
                st.markdown(topic_html, unsafe_allow_html=True)

            # Evidence section
            evidence = row.get("evidence", {})
            if evidence:
                st.markdown("---")
                st.markdown("**Evidence:**")

                if evidence.get("matched_topics"):
                    st.markdown("**Matched Topics:**")
                    mt_html = " ".join([f'<span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:3px;margin:2px;font-size:0.8em;">{t}</span>' for t in evidence["matched_topics"]])
                    st.markdown(mt_html, unsafe_allow_html=True)

                if evidence.get("matched_keywords"):
                    st.markdown("**Matched Keywords:**")
                    mk_html = " ".join([f'<span style="background:#dbeafe;color:#1e40af;padding:2px 6px;border-radius:3px;margin:2px;font-size:0.8em;">{k}</span>' for k in evidence["matched_keywords"]])
                    st.markdown(mk_html, unsafe_allow_html=True)

                if evidence.get("matched_queries"):
                    st.markdown("**Matched Queries:**")
                    for q in evidence["matched_queries"]:
                        st.caption(f"`{q}`")

                st.caption(f"README used: {'Yes' if evidence.get('readme_snippet_used') else 'No'}")

        with col2:
            st.markdown(f"**Stars:** {row['stargazers_count']}")
            st.markdown(f"**Forks:** {row['forks_count']}")
            st.markdown(f"**Open Issues:** {row['open_issues_count']}")
            st.markdown(f"**Language:** {row['language'] or 'N/A'}")
            st.markdown(f"**Updated:** {row['updated_at'][:10]}")

            st.link_button("🔗 Open on GitHub", row["html_url"], use_container_width=True)

            # Skills as badges
            if row["skills"]:
                st.markdown("**Skills:**")
                skills_html = " ".join([f'<span style="background:#e0e7ff;color:#3730a3;padding:2px 6px;border-radius:3px;margin:2px;font-size:0.8em;">{s}</span>' for s in row["skills"]])
                st.markdown(skills_html, unsafe_allow_html=True)


def main():
    # Header
    st.title("🔍 SAP GitHub Repos Finder")
    st.caption("Top 25 SAP-related repositories — curated, classified, updated weekly")

    # Load data
    df, generated_at = load_repos()

    if df is None:
        st.error(f"❌ {generated_at}")
        st.info("""
        **To fix:**
        1. Run locally: `export GITHUB_TOKEN=xxx && python fetch_sap_repos.py`
        2. Or wait for the weekly GitHub Action (runs Mondays 6 AM UTC)
        3. Check [GitHub Actions](../../actions) for run logs
        """)
        return

    if df.empty:
        st.warning(f"⚠️ No repositories found. Last run: {generated_at}")
        return

    # Last updated timestamp
    try:
        dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        st.caption(f"📅 Data last updated: {dt.strftime('%Y-%m-%d %H:%M UTC')}")
    except Exception:
        st.caption(f"📅 Data last updated: {generated_at}")

    # Sidebar filters
    with st.sidebar:
        st.header("🔎 Filters")

        # Area multiselect
        selected_areas = st.multiselect(
            "Filter by SAP Area",
            options=["All"] + SAP_AREAS,
            default=["All"],
            help="Select one or more SAP areas to filter repositories"
        )

        # Keyword search
        search_query = st.text_input(
            "Search skills/keywords",
            placeholder="e.g., CDS, RAG, migration...",
            help="Searches skills, purpose, what_it_offers, topics, name, description"
        )

        st.divider()

        # Export buttons
        st.subheader("📥 Export")
        filtered_df = filter_repos(df, selected_areas, search_query)

        if not filtered_df.empty:
            # CSV export
            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📊 Export CSV (filtered)",
                csv,
                f"sap_repos_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )

            # JSON export
            json_str = filtered_df.to_json(orient="records", indent=2, force_ascii=False)
            st.download_button(
                "📄 Export JSON (filtered)",
                json_str,
                f"sap_repos_{datetime.now().strftime('%Y%m%d')}.json",
                "application/json",
                use_container_width=True
            )
        else:
            st.caption("No results to export")

        st.divider()
        st.caption(f"Showing {len(filtered_df)} of {len(df)} repositories")

    # Main table
    if filtered_df.empty:
        st.info("No repositories match your filters. Try adjusting the filters.")
        return

    # Prepare display DataFrame
    display_df = filtered_df.copy()
    display_df["Rank"] = range(1, len(display_df) + 1)
    display_df["Repo"] = display_df["full_name"].apply(lambda x: f"[{x}](https://github.com/{x})")
    display_df["Stars"] = display_df["stargazers_count"]
    display_df["Primary Area"] = display_df["primary_area"]
    display_df["What It Offers"] = display_df["what_it_offers"]
    display_df["Skills"] = display_df["skills"].apply(format_skills)
    display_df["Purpose"] = display_df["purpose"]
    display_df["Updated"] = display_df["updated_at"].str[:10]

    # Column config for st.dataframe
    column_config = {
        "Rank": st.column_config.NumberColumn("Rank", width="small"),
        "Repo": st.column_config.LinkColumn("Repository", width="medium"),
        "Stars": st.column_config.NumberColumn("⭐ Stars", width="small"),
        "Primary Area": st.column_config.TextColumn("Area", width="small"),
        "What It Offers": st.column_config.TextColumn("What It Offers", width="large"),
        "Skills": st.column_config.TextColumn("Skills", width="medium"),
        "Purpose": st.column_config.TextColumn("Purpose", width="large"),
        "Updated": st.column_config.DateColumn("Updated", width="small", format="YYYY-MM-DD"),
    }

    # Show table (hide original columns)
    hidden_cols = [c for c in display_df.columns if c not in column_config]
    st.dataframe(
        display_df.drop(columns=hidden_cols),
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=600,
    )

    st.divider()

    # Detail expanders (below table)
    st.subheader("📋 Repository Details")
    st.caption("Click a row above to expand details below, or scroll through cards:")

    for _, row in filtered_df.iterrows():
        render_repo_card(row)


if __name__ == "__main__":
    main()