from datetime import date, datetime
from typing import Dict, Optional

import streamlit as st


def render_filter_panel(regions: list[str]) -> Dict[str, Optional[datetime] | str | bool]:
    st.sidebar.header("Filters")

    region_options = [""] + sorted([r for r in regions if r])
    region = st.sidebar.selectbox(
        "Region",
        options=region_options,
        index=0,
        help="Choose a predicted region label.",
    )

    keyword = st.sidebar.text_input("Keyword filter", value="", placeholder="name, city, niche...")
    collection_keyword = st.sidebar.text_input(
        "Collection keyword",
        value="",
        placeholder="branding, ui, food...",
    )
    interacted_only = st.sidebar.checkbox("Only accounts with likes/saves", value=False)

    use_date_filter = st.sidebar.checkbox("Use follow date range", value=False)
    date_start = None
    date_end = None
    if use_date_filter:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_value = st.date_input("Start", value=date(2018, 1, 1))
        with col2:
            end_value = st.date_input("End", value=date.today())
        date_start = datetime.combine(start_value, datetime.min.time())
        date_end = datetime.combine(end_value, datetime.min.time())

    return {
        "region": region,
        "keyword": keyword,
        "collection_keyword": collection_keyword,
        "interacted_only": interacted_only,
        "date_start": date_start,
        "date_end": date_end,
    }
