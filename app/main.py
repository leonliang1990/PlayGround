from pathlib import Path

import streamlit as st

from app.ui_filters import render_filter_panel
from app.ui_search import render_result_cards, render_search_box
from core.classify.region_classifier import RegionClassifier
from core.importers.instagram_export import load_follow_records, load_interest_signals, load_metadata_csv
from core.services.avatar_service import AvatarService
from core.services.filter_service import filter_records
from core.services.profile_metadata_service import ProfileMetadataService
from core.services.similarity_service import rank_by_similarity
from core.storage.sqlite_repo import SQLiteRepo


st.set_page_config(page_title="IG Following Filter", layout="wide")
st.title("Instagram Following Filter (Local)")
st.caption("Local-only tool for importing, filtering, and searching accounts you follow.")

db_path = str(Path("data") / "app.db")
repo = SQLiteRepo(db_path)
classifier = RegionClassifier()
avatar_service = AvatarService(repo)
metadata_service = ProfileMetadataService()

tab_import, tab_search = st.tabs(["Import", "Browse & Search"])

with tab_import:
    st.subheader("Import Instagram export")
    input_path = st.text_input(
        "Export path (file or folder)",
        placeholder=r"D:\Downloads\instagram_export",
    )
    metadata_csv = st.text_input(
        "Optional metadata CSV path",
        placeholder=r"D:\Downloads\profile_metadata.csv",
    )

    if st.button("Run import", type="primary"):
        try:
            records = load_follow_records(input_path)
            interaction_signals = load_interest_signals(input_path)
            if metadata_csv.strip():
                metadata = load_metadata_csv(metadata_csv.strip())
                for record in records:
                    info = metadata.get(record.username)
                    if not info:
                        continue
                    record.bio = info.get("bio", "")
                    record.full_name = info.get("full_name", "")
                    record.location = info.get("location", "")
                    record.profession = info.get("profession", "")

            for record in records:
                record.inferred_region = classifier.infer_for_record(record)
                signal = interaction_signals.get(record.username, {})
                record.likes_count = int(signal.get("likes_count", 0))
                record.saved_count = int(signal.get("saved_count", 0))
                record.collection_tags = str(signal.get("collection_tags", ""))

            repo.upsert_records(records)
            interacted = sum(1 for r in records if r.likes_count > 0 or r.saved_count > 0)
            st.success(
                f"Imported/updated {len(records)} accounts. "
                f"Detected interaction signals for {interacted} accounts."
            )
        except Exception as exc:
            st.error(f"Import failed: {exc}")

    st.divider()
    st.subheader("Generate metadata draft (semi-auto)")
    st.caption("Fetches public profile info and exports a draft CSV for manual cleanup.")
    output_csv = st.text_input(
        "Draft CSV output path",
        value=str(Path("data") / "metadata_generated.csv"),
    )
    col_a, col_b = st.columns(2)
    with col_a:
        max_accounts = st.slider("Max accounts to fetch", min_value=20, max_value=1000, value=300, step=20)
    with col_b:
        delay_seconds = st.slider("Delay between requests (seconds)", min_value=0.2, max_value=2.0, value=0.8, step=0.1)

    if st.button("Generate metadata draft CSV"):
        try:
            existing = repo.list_records()
            if not existing:
                st.warning("No following records yet. Import first, then generate metadata.")
            else:
                usernames = [r.get("username", "") for r in existing]
                result = metadata_service.generate_metadata_csv(
                    usernames,
                    output_csv,
                    max_accounts=max_accounts,
                    delay_seconds=delay_seconds,
                )
                st.success(
                    f"Draft saved: {result['output_path']} | "
                    f"Attempted: {result['attempted']} | "
                    f"Filled: {result['success']}"
                )
        except Exception as exc:
            st.error(f"Draft generation failed: {exc}")

with tab_search:
    st.subheader("Filter + Similarity Search")
    all_records = repo.list_records()
    st.caption(f"Local records: {len(all_records)}")

    if not all_records:
        st.info("No data yet. Go to Import tab first.")
    else:
        regions = list({r.get("inferred_region", "") for r in all_records})
        filters = render_filter_panel(regions)
        query = render_search_box()
        top_k = st.slider("Top K", min_value=10, max_value=200, value=50, step=10)

        filtered = filter_records(
            all_records,
            region=filters["region"],
            text_keyword=filters["keyword"],
            collection_keyword=filters["collection_keyword"],
            interacted_only=bool(filters["interacted_only"]),
            date_start=filters["date_start"],
            date_end=filters["date_end"],
        )

        if query.strip():
            final_records = rank_by_similarity(filtered, query, limit=top_k)
        else:
            final_records = filtered[:top_k]

        st.write(f"Matched records: {len(final_records)}")
        render_result_cards(final_records, avatar_service)
