"""Lightweight theme helpers for Streamlit."""

from __future__ import annotations

import streamlit as st


def inject_theme() -> None:
    """Inject a minimal neutral dashboard theme."""
    st.markdown(
        """
        <style>
          .stApp {
            background:
              radial-gradient(circle at top right, rgba(15, 23, 42, 0.03), transparent 20%),
              linear-gradient(180deg, #f7f8fa 0%, #f4f6f8 100%);
          }

          div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid #e7eaee;
            border-radius: 18px;
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
          }

          div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid #e8ebef;
            border-radius: 20px;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
          }

          .fd-card,
          .fd-empty-state {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid #e8ebef;
            border-radius: 20px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
            margin-bottom: 1rem;
          }

          .fd-card__header {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
            margin-bottom: 0.9rem;
          }

          .fd-card__title {
            font-size: 1rem;
            font-weight: 600;
            color: #18212f;
          }

          .fd-card__meta {
            color: #667085;
            font-size: 0.9rem;
          }

          .fd-card__body {
            display: grid;
            gap: 0.4rem;
            color: #344054;
            font-size: 0.92rem;
          }

          .fd-badge {
            background: #eef2f6;
            color: #425466;
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            font-size: 0.8rem;
            white-space: nowrap;
          }

          .fd-empty-state h3 {
            margin: 0 0 0.4rem 0;
            color: #18212f;
          }

          .fd-empty-state p {
            margin: 0;
            color: #526071;
            max-width: 42rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
