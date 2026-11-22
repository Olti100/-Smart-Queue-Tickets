import streamlit as st


def success(message: str):
    st.success(message)


def error(message: str):
    st.error(message)


def warning(message: str):
    st.warning(message)
