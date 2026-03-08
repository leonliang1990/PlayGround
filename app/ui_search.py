from datetime import datetime
from typing import Dict, List

import streamlit as st

from core.services.avatar_service import AvatarService


def _format_followed_at(ts: int | None) -> str:
    if ts is None:
        return "-"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def render_search_box() -> str:
    return st.text_input(
        "Search best matches",
        placeholder="Try: designer, seoul, ux tokyo, ny photographer...",
    )


def render_result_cards(records: List[Dict], avatar_service: AvatarService) -> None:
    if not records:
        st.info("No records match current filters/search.")
        return

    for item in records:
        username = item.get("username", "")
        profile_url = item.get("profile_url") or f"https://www.instagram.com/{username}/"
        with st.container(border=True):
            left, mid = st.columns([1, 5])

            with left:
                session_key = f"avatar_url_{username}"
                avatar_url = st.session_state.get(session_key)
                if avatar_url:
                    st.image(avatar_url, width=88)
                else:
                    st.caption("No avatar")
                if st.button("Load avatar", key=f"btn_avatar_{username}"):
                    loaded = avatar_service.get_avatar_url(username)
                    if loaded:
                        st.session_state[session_key] = loaded
                    st.rerun()

            with mid:
                score = item.get("similarity_score")
                if score is not None:
                    st.markdown(f"**[@{username}]({profile_url})**  |  Match: `{score}`")
                else:
                    st.markdown(f"**[@{username}]({profile_url})**")
                st.caption(
                    f"Region: {item.get('inferred_region') or '-'} | "
                    f"Profession: {item.get('profession') or '-'} | "
                    f"Followed: {_format_followed_at(item.get('followed_at'))}"
                )
                st.caption(
                    f"Likes: {int(item.get('likes_count') or 0)} | "
                    f"Saved: {int(item.get('saved_count') or 0)}"
                )
                tags = (item.get("collection_tags") or "").strip()
                if tags:
                    st.caption(f"Collections: {tags}")
                bio = item.get("bio") or ""
                if bio:
                    st.write(bio)
                else:
                    st.write("_No bio metadata yet_")
