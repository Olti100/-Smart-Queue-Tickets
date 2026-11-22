import streamlit as st


def dataframe_table(df, title: str):
    st.subheader(title)
    st.dataframe(df, use_container_width=True, hide_index=True)
