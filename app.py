"""ProcureFlow Streamlit application entry point."""

import streamlit as st

from views.dashboard import render_dashboard
from views.requests import render_requests


st.set_page_config(
    page_title="ProcureFlow | Procurement Operations",
    page_icon=":material/account_tree:",
    layout="wide",
    initial_sidebar_state="expanded",
)

dashboard = st.Page(
    render_dashboard,
    title="Dashboard",
    icon=":material/space_dashboard:",
    default=True,
)
requests = st.Page(
    render_requests,
    title="Requests",
    icon=":material/list_alt:",
)
navigation = st.navigation([dashboard, requests], position="sidebar")
navigation.run()
